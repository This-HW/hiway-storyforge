import unittest

from storyforge import rules


class TestCopyFormat(unittest.TestCase):
    def test_valid_range(self):
        self.assertEqual(rules.validate_copy_format("키 작고 뚱뚱해서 따돌림 당하던 아기 코끼리"), [])

    def test_too_short(self):
        self.assertTrue(rules.validate_copy_format("짧은 문장"))

    def test_too_long(self):
        self.assertTrue(rules.validate_copy_format("가" * 29))

    def test_too_many_lines(self):
        self.assertTrue(rules.validate_copy_format("첫째줄입니다요\n둘째줄입니다요\n셋째줄입니다요"))

    def test_spaces_excluded_from_count(self):
        self.assertEqual(rules.char_count("a b c"), 3)


class TestScreening(unittest.TestCase):
    def test_engagement_bait_detected(self):
        findings = rules.screen_copy("이거 보면 좋아요 눌러주세요")
        self.assertTrue(any("참여 유도" in f for f in findings))

    def test_medical_definitive_detected(self):
        findings = rules.screen_copy("이거 먹으면 바로 낫습니다 100% 효과")
        self.assertTrue(any("의학" in f for f in findings))

    def test_clean_copy_passes(self):
        self.assertEqual(rules.screen_copy("10년째 이것만 먹은 남자의 몸"), [])


class TestExportGate(unittest.TestCase):
    def test_rights_unusable_blocks(self):
        blockers = rules.export_blockers("사용불가", {"auto_findings": []},
                                         rules.MANUAL_CHECK_ITEMS)
        self.assertTrue(blockers)

    def test_all_clear(self):
        blockers = rules.export_blockers("확인됨", {"auto_findings": []},
                                         rules.MANUAL_CHECK_ITEMS)
        self.assertEqual(blockers, [])

    def test_missing_manual_check_blocks(self):
        blockers = rules.export_blockers("확인됨", {"auto_findings": []}, [])
        self.assertTrue(blockers)


if __name__ == "__main__":
    unittest.main()
