
from django.test import SimpleTestCase

from .entity_extractor import extract_entities
from .preprocessing import normalize_text, tokenize, token_set


class EntityExtractorTests(SimpleTestCase):

    def test_extracts_mri_and_time(self):
        result = extract_entities("My MRI scan is tomorrow at 10 AM")

        self.assertEqual(result["procedure"], ["mri"])
        self.assertEqual(result["procedure_id"], 14)
        self.assertEqual(result["procedure_candidates"], [14])
        self.assertEqual(result["time"], ["10 am"])

    def test_extracts_ct(self):
        result = extract_entities("I have a CT scan tomorrow")

        self.assertEqual(result["procedure"], ["ct"])
        self.assertEqual(result["procedure_id"], 12)

    def test_extracts_ecg(self):
        result = extract_entities("I need an ECG")

        self.assertEqual(result["procedure_id"], 9)

    def test_extracts_colonoscopy(self):
        result = extract_entities("My colonoscopy is tomorrow")

        self.assertEqual(result["procedure_id"], 11)

    def test_endoscopy_and_colonoscopy_share_protocol(self):
        result = extract_entities(
            "My colonoscopy and endoscopy are scheduled"
        )

        self.assertEqual(result["procedure_id"], 11)
        self.assertEqual(result["procedure_candidates"], [11])

    def test_extracts_xray(self):
        result = extract_entities("I have an X-ray appointment")

        self.assertEqual(result["procedure_id"], 13)

    def test_extracts_english_aliases(self):
        cases = {
            "computed tomography": 12,
            "electrocardiogram": 9,
            "magnetic resonance imaging": 14,
        }

        for phrase, expected_id in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    extract_entities(phrase)["procedure_id"],
                    expected_id,
                )

    def test_extracts_hindi_aliases(self):
        cases = {
            "मेरी कोलोनोस्कोपी है": 11,
            "एंडोस्कोपी होने वाली है": 11,
            "सीटी स्कैन": 12,
            "ईसीजी करवाना है": 9,
            "एक्स-रे": 13,
            "एक्स रे": 13,
            "एक्सरे": 13,
            "एमआरआई": 14,
        }

        for phrase, expected_id in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    extract_entities(phrase)["procedure_id"],
                    expected_id,
                )

    def test_hindi_ct_alias_requires_medical_context(self):
        medical_cases = (
            "सीटी स्कैन",
            "मेरी सीटी की appointment है",
        )

        ordinary_cases = (
            "बाहर सीटी बज रही है",
            "सीटी की आवाज आ रही है",
        )

        for phrase in medical_cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    extract_entities(phrase)["procedure_id"],
                    12,
                )

        for phrase in ordinary_cases:
            with self.subTest(phrase=phrase):
                self.assertIsNone(
                    extract_entities(phrase)["procedure_id"],
                )

    def test_extracts_hinglish_aliases(self):
        cases = {
            "meri colonoscopy hai": 11,
            "CT scan ke liye": 12,
            "ECG karwana hai": 9,
            "X-ray se pehle": 13,
            "MRI room mein": 14,
        }

        for phrase, expected_id in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    extract_entities(phrase)["procedure_id"],
                    expected_id,
                )

    def test_ambiguous_scan_does_not_select_procedure(self):
        result = extract_entities("scan karwana hai")

        self.assertIsNone(result["procedure_id"])
        self.assertEqual(result["procedure_candidates"], [])

    def test_generic_references_do_not_select_procedure(self):
        for phrase in (
            "my appointment",
            "the procedure",
            "वही",
            "यह",
        ):
            with self.subTest(phrase=phrase):
                result = extract_entities(phrase)
                self.assertIsNone(result["procedure_id"])

    def test_multiple_procedures_require_clarification(self):
        cases = (
            "CT scan aur MRI",
            "ECG ke baad X-ray",
            "मेरी MRI और CT दोनों हैं",
        )

        for phrase in cases:
            with self.subTest(phrase=phrase):
                result = extract_entities(phrase)
                self.assertIsNone(result["procedure_id"])
                self.assertGreaterEqual(
                    len(result["procedure_candidates"]),
                    2,
                )

    def test_extracts_multiple_time_formats(self):
        result = extract_entities(
            "My appointment is at 10:30 AM, not noon"
        )

        self.assertEqual(result["time"], ["10:30", "noon"])

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            extract_entities(None)


class PreprocessingTests(SimpleTestCase):

    def test_normalizes_whitespace_and_case(self):
        self.assertEqual(
            normalize_text("  MRI   Scan  "),
            "mri scan",
        )

    def test_tokenizes_english_text(self):
        self.assertEqual(
            tokenize("MRI scan at 10 AM"),
            ["mri", "scan", "at", "10", "am"],
        )

    def test_creates_token_set(self):
        self.assertEqual(
            token_set("MRI scan MRI"),
            {"mri", "scan"},
        )

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            normalize_text(None)
