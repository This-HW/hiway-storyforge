import unittest

from storyforge import gates
from storyforge.prompting import build_slide_prompt


def _story(**overrides):
    story = {
        "title": "테스트 이야기",
        "continuity": {
            "identity": "작은 갈색 강아지, 처진 귀",
            "age_timeline": {"1": "생후 2주", "4": "3개월", "8": "1살"},
            "env_markers": ["오래된 골목"],
            "props": ["빨간 목줄"],
            "light_palette": "golden backlight, creamy bokeh",
        },
        "slides": [
            {"n": 1, "text": "비 오는 날 길에서 만난 작은 강아지 이야기",
             "image_prompt": "a passerby wraps a wet puppy in a towel, "
                             "show both beneath the awning, golden backlight, creamy bokeh, "
                             "photorealistic, no text"},
            {"n": 2, "text": "강아지는 비를 맞으며 떨고 있었어요",
             "image_prompt": "puppy shivering in the rain, golden backlight, "
                             "bokeh, photorealistic, no text"},
        ],
        "caption": "비 오는 날 길에서 만난 작은 강아지 이야기\n\n"
                   "강아지는 비를 맞으며 떨고 있었어요.\n\n"
                   "원본 출처: @example\n\n"
                   "#동물스타그램 #감동스토리 #animalstories",
    }
    story.update(overrides)
    return story


def _gates_of(findings):
    return [f["gate"] for f in findings]


class TestSlideTexts(unittest.TestCase):
    def test_empty_text_is_error(self):
        findings = gates.check_slide_texts([{"n": 1, "text": "  "}])
        self.assertIn("slide_text_empty", _gates_of(findings))

    def test_duplicate_text_is_error(self):
        slides = [{"n": 1, "text": "비 오는 날 길에서 만난 작은 강아지 이야기"},
                  {"n": 2, "text": "강아지는 비를 맞으며 떨고 있었어요"},
                  {"n": 3, "text": "강아지는 비를 맞으며 떨고 있었어요"}]
        self.assertIn("slide_text_duplicate", _gates_of(gates.check_slide_texts(slides)))

    def test_adjacent_opening_duplicate_is_error(self):
        slides = [{"n": 1, "text": "비 오는 날 길에서 만난 작은 강아지 이야기"},
                  {"n": 2, "text": "작은 강아지가 오늘도 길을 걸었어요"},
                  {"n": 3, "text": "작은 강아지가 오늘도 집을 찾았어요"}]
        self.assertIn("adjacent_opening_duplicate",
                      _gates_of(gates.check_slide_texts(slides)))

    def test_overlong_slide_is_error(self):
        long_text = "가" * 50
        findings = gates.check_slide_texts(
            [{"n": 1, "text": "비 오는 날 길에서 만난 작은 강아지 이야기"},
             {"n": 2, "text": long_text}])
        self.assertIn("slide_text_length", _gates_of(findings))

    def test_hook_length_warning(self):
        findings = gates.check_slide_texts([{"n": 1, "text": "짧은 후킹"}])
        self.assertIn("hook_length", _gates_of(findings))

    def test_monotone_endings_warning(self):
        slides = [{"n": 1, "text": "비 오는 날 길에서 만난 작은 강아지 이야기"},
                  {"n": 2, "text": "오늘도 밥을 잘 먹었어요"},
                  {"n": 3, "text": "내일도 밥을 잘 먹었어요"},
                  {"n": 4, "text": "매일 밥을 잘 먹었어요"}]
        self.assertIn("monotone_endings", _gates_of(gates.check_slide_texts(slides)))

    def test_too_many_lines_is_error(self):
        findings = gates.check_slide_texts(
            [{"n": 1, "text": "한 줄\n두 줄\n세 줄"}])
        self.assertIn("slide_text_lines", _gates_of(findings))


class TestCaption(unittest.TestCase):
    GOOD = ("비 오는 날 길에서 만난 작은 강아지 이야기\n\n"
            "강아지는 비를 맞으며 떨고 있었어요.\n\n"
            "원본 출처: @example\n\n"
            "#동물스타그램 #감동스토리 #animalstories")

    def test_good_caption_passes(self):
        findings = gates.check_caption(self.GOOD)
        self.assertEqual([f for f in findings if f["level"] == "error"], [])

    def test_emoji_banned_by_default(self):
        findings = gates.check_caption(self.GOOD + "\n💬 댓글로 알려주세요")
        self.assertIn("emoji_policy", _gates_of(findings))

    def test_emoji_allowlist(self):
        findings = gates.check_caption(self.GOOD + "\n💬 댓글로 알려주세요",
                                       emoji_policy=["💬"])
        self.assertNotIn("emoji_policy", _gates_of(findings))

    def test_url_is_error_for_animal(self):
        findings = gates.check_caption(self.GOOD + "\nhttps://example.com/story")
        self.assertIn("caption_url", _gates_of(findings))

    def test_formal_ending_is_error(self):
        findings = gates.check_caption(
            self.GOOD.replace("떨고 있었어요", "떨고 있었습니다"))
        self.assertIn("formal_ending", _gates_of(findings))

    def test_missing_source_line_is_error(self):
        findings = gates.check_caption(self.GOOD.replace("원본 출처: @example\n\n", ""))
        self.assertIn("source_line_missing", _gates_of(findings))

    def test_hashtag_count_warning(self):
        findings = gates.check_caption(self.GOOD.replace(
            "#동물스타그램 #감동스토리 #animalstories", "#동물스타그램"))
        self.assertIn("hashtag_count", _gates_of(findings))

    def test_property_caption_skips_source_and_url_is_warning(self):
        caption = ("고지서 보고 '왜 이 금액이죠?'\n\n"
                   "분담 기준을 정하면 분쟁이 줄어요.\n\n"
                   "#부동산관리 #PMS #propertyeasy")
        findings = gates.check_caption(caption, channel_format="property")
        self.assertNotIn("source_line_missing", _gates_of(findings))
        self.assertEqual([f for f in findings if f["level"] == "error"], [])


class TestPrompts(unittest.TestCase):
    def test_tone_token_missing(self):
        story = _story(slides=[
            {"n": 1, "text": "x",
             "image_prompt": "puppy, two-thirds, looking at the camera, bokeh, photorealistic, no text"},
        ])
        findings = gates.check_prompts(story)
        self.assertTrue(any(f["gate"] == "tone_token_missing" and "golden backlight" in f["detail"]
                            for f in findings))

    def test_photoreal_and_no_text_missing(self):
        story = _story(slides=[
            {"n": 1, "text": "x",
             "image_prompt": "puppy, two-thirds, looking at the camera, golden backlight, bokeh"},
        ])
        found = _gates_of(gates.check_prompts(story))
        self.assertIn("photoreal_missing", found)
        self.assertIn("no_text_missing", found)

    def test_story_action_is_valid_without_closeup_markers(self):
        self.assertFalse(any(f["level"] == "error" for f in gates.check_prompts(_story())))

    def test_legacy_fixed_face_size_is_a_warning(self):
        story = _story()
        story["slides"][0]["image_prompt"] += ", face fills two-thirds of frame"
        findings = gates.check_prompts(story)
        self.assertEqual([f["slide"] for f in findings
                          if f["gate"] == "slide1_legacy_face_framing"], [1])
        self.assertFalse(any(f["level"] == "error" for f in findings))

    def test_custom_framing_marker_is_still_required_when_configured(self):
        story = _story(slides=[
            {"n": 1, "text": "x",
             "image_prompt": "puppy in a garden, golden backlight, bokeh, photorealistic, no text"},
        ])
        findings = gates.check_prompts(story, framing_markers=("medium shot",))
        self.assertIn("slide1_framing", _gates_of(findings))

    def test_missing_prompt_is_error(self):
        story = _story(slides=[{"n": 1, "text": "x"}])
        self.assertIn("prompt_missing", _gates_of(gates.check_prompts(story)))

    def test_no_ref_metadata_warns(self):
        story = _story()
        findings = gates.check_prompts(story)
        self.assertTrue(any(f["gate"] == "continuity_refs" and f["level"] == "warning"
                            for f in findings))

    def test_ref_chain_previous_slide(self):
        story = _story(slides=[
            {"n": 1, "text": "x", "refs": [],
             "image_prompt": "puppy, two-thirds, looking at the camera, golden backlight, bokeh, photorealistic, no text"},
            {"n": 2, "text": "y", "refs": [1],
             "image_prompt": "puppy, golden backlight, bokeh, photorealistic, no text"},
            {"n": 3, "text": "z", "refs": [1],
             "image_prompt": "puppy, golden backlight, bokeh, photorealistic, no text"},
        ])
        findings = gates.check_prompts(story)
        self.assertTrue(any(f["gate"] == "continuity_refs" and f["slide"] == 3
                            for f in findings))


class TestContinuity(unittest.TestCase):
    def test_missing_block_is_error(self):
        self.assertIn("continuity_missing",
                      _gates_of(gates.check_continuity({"slides": []})))

    def test_missing_field_is_error(self):
        story = _story()
        del story["continuity"]["props"]
        self.assertIn("continuity_field_missing",
                      _gates_of(gates.check_continuity(story)))

    def test_age_regression_is_warning_flashback_possible(self):
        # Hook-then-flashback is a standard structure, so a decrease is a
        # confirm-it's-intentional warning, not a hard error.
        story = _story()
        story["continuity"]["age_timeline"] = {"1": "1살", "2": "3개월"}
        findings = gates.check_continuity(story)
        matches = [f for f in findings if f["gate"] == "age_regression"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["level"], "warning")

    def test_calendar_year_is_not_an_age(self):
        story = _story()
        story["continuity"]["age_timeline"] = {"1": "2012년생 새끼", "2": "3살"}
        findings = gates.check_continuity(story)
        self.assertFalse(any(f["gate"] == "age_regression" for f in findings))

    def test_empty_props_list_is_warning_not_error(self):
        story = _story()
        story["continuity"]["props"] = []
        findings = gates.check_continuity(story)
        matches = [f for f in findings if f["gate"] == "continuity_field_empty"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["level"], "warning")
        self.assertFalse(any(f["gate"] == "continuity_field_missing"
                             for f in findings))

    def test_qualitative_young_ages_order_before_adult(self):
        story = _story()
        story["continuity"]["age_timeline"] = {
            "1": "새끼 (2012)", "2": "어린 돼지 (성장 중)", "3": "성체"}
        findings = gates.check_continuity(story)
        self.assertFalse(any(f["gate"] == "age_regression" for f in findings))
        self.assertFalse(any(f["gate"] == "age_unparseable" for f in findings))

    def test_elderly_marker_orders_after_adult(self):
        story = _story()
        story["continuity"]["age_timeline"] = {"1": "성체", "8": "노견(추모)"}
        findings = gates.check_continuity(story)
        self.assertFalse(any(f["gate"] == "age_regression" for f in findings))

    def test_age_progression_passes(self):
        story = _story()
        self.assertNotIn("age_regression", _gates_of(gates.check_continuity(story)))

    def test_adult_marker_orders_last(self):
        story = _story()
        story["continuity"]["age_timeline"] = {"1": "3개월", "8": "성묘가 됐어요"}
        self.assertNotIn("age_regression", _gates_of(gates.check_continuity(story)))

    def test_missing_timeline_warns(self):
        story = _story()
        del story["continuity"]["age_timeline"]
        findings = gates.check_continuity(story)
        self.assertTrue(any(f["gate"] == "age_timeline_missing" and f["level"] == "warning"
                            for f in findings))


class TestRunAll(unittest.TestCase):
    def test_clean_story_passes_with_checklist(self):
        result = gates.run_all(_story())
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], 0)
        self.assertGreaterEqual(len(result["checklist"]), 10)
        self.assertTrue(any("§1.10" in item["gate"] for item in result["checklist"]))
        self.assertTrue(any("§1.11" in item["gate"] for item in result["checklist"]))

    def test_emoji_caption_fails(self):
        story = _story(caption="비 오는 날 길에서 만난 작은 강아지 이야기\n\n💬 댓글로 알려주세요")
        result = gates.run_all(story)
        self.assertFalse(result["passed"])
        self.assertGreater(result["errors"], 0)


class TestPrompting(unittest.TestCase):
    TONE = {"tokens": ["golden backlight", "bokeh"],
            "photoreal": "photorealistic",
            "no_text": "no text"}
    CONT = {"identity": "small brown puppy with floppy ears",
            "env_markers": ["old alley"],
            "props": ["red collar"],
            "light_palette": "warm evening light"}

    def test_slide1_has_anchor_framing_and_tone(self):
        prompt = build_slide_prompt(action="puppy shivering in the rain",
                                    continuity=self.CONT, tone=self.TONE, slide_n=1)
        self.assertIn("small brown puppy", prompt)
        self.assertIn("puppy shivering in the rain", prompt)
        self.assertIn("key action or relationship", prompt)
        self.assertIn("lower third for a caption", prompt)
        self.assertNotIn("two-thirds", prompt)
        self.assertIn("golden backlight", prompt)
        self.assertIn("photorealistic", prompt)
        self.assertIn("no text", prompt)

    def test_cover_can_use_framing_specific_to_its_story(self):
        prompt = build_slide_prompt(
            action="a hippo calf suckles from a bottle held by a carer",
            tone={**self.TONE, "framing_slide1": "medium shot showing calf and bottle"},
        )
        self.assertIn("medium shot showing calf and bottle", prompt)

    def test_later_slide_has_no_identity_anchor_by_default(self):
        prompt = build_slide_prompt(action="puppy sleeping",
                                    continuity=self.CONT, tone=self.TONE, slide_n=3)
        self.assertNotIn("floppy ears", prompt)
        self.assertIn("old alley", prompt)
        self.assertIn("golden backlight", prompt)
        self.assertNotIn("lower third for a caption", prompt)

    def test_no_duplicated_tokens(self):
        prompt = build_slide_prompt(
            action="puppy in golden backlight",
            continuity=self.CONT, tone=self.TONE, slide_n=2)
        self.assertEqual(prompt.lower().count("golden backlight"), 1)

    def test_anchor_all_includes_identity_everywhere(self):
        prompt = build_slide_prompt(action="puppy sleeping",
                                    continuity=self.CONT, tone=self.TONE,
                                    slide_n=5, anchor_on="all")
        self.assertIn("small brown puppy", prompt)


if __name__ == "__main__":
    unittest.main()
