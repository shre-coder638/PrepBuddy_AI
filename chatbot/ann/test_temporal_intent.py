from django.test import SimpleTestCase

from .temporal_intent import detect_temporal_intent


class TemporalIntentTests(SimpleTestCase):

    def test_english_results_followup(self):
        self.assertEqual(
            detect_temporal_intent("When will I get my MRI results?"),
            "results_followup",
        )

    def test_english_during_scan(self):
        self.assertEqual(
            detect_temporal_intent("What happens during the MRI scan?"),
            "during_scan",
        )

    def test_unrelated_appointment_question_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("What happens during my appointment?")
        )

    def test_unrelated_hospital_question_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("What should I do inside the hospital?")
        )

    def test_english_post_scan_discharge(self):
        self.assertEqual(
            detect_temporal_intent("Can I drive after the MRI scan?"),
            "post_scan_discharge",
        )

    def test_hindi_results_followup(self):
        question = "\u092e\u0941\u091d\u0947 \u090f\u092e\u0906\u0930\u0906\u0908 \u0915\u0940 \u0930\u093f\u092a\u094b\u0930\u094d\u091f \u0915\u092c \u092e\u093f\u0932\u0947\u0917\u0940?"
        self.assertEqual(
            detect_temporal_intent(question),
            "results_followup",
        )

    def test_hindi_during_scan(self):
        question = "\u090f\u092e\u0906\u0930\u0906\u0908 \u0938\u094d\u0915\u0948\u0928 \u0915\u0947 \u0926\u094c\u0930\u093e\u0928 \u092e\u0941\u091d\u0947 \u092e\u0926\u0926 \u091a\u093e\u0939\u093f\u090f \u0924\u094b \u0915\u094d\u092f\u093e \u0915\u0930\u0942\u0901?"
        self.assertEqual(
            detect_temporal_intent(question),
            "during_scan",
        )

    def test_hindi_post_scan_discharge(self):
        question = "\u0938\u094d\u0915\u0948\u0928 \u0915\u0947 \u092c\u093e\u0926 \u0915\u094d\u092f\u093e \u092e\u0948\u0902 \u0918\u0930 \u091c\u093e \u0938\u0915\u0924\u093e \u0939\u0942\u0901?"
        self.assertEqual(
            detect_temporal_intent(question),
            "post_scan_discharge",
        )

    def test_hinglish_results_followup(self):
        self.assertEqual(
            detect_temporal_intent("Mujhe MRI ki report kab milegi?"),
            "results_followup",
        )

    def test_hinglish_during_scan(self):
        self.assertEqual(
            detect_temporal_intent("MRI scan ke dauran help chahiye toh kya karun?"),
            "during_scan",
        )

    def test_hinglish_post_scan_discharge(self):
        self.assertEqual(
            detect_temporal_intent("MRI scan ke baad kya main ghar ja sakta hoon?"),
            "post_scan_discharge",
        )

    def test_generic_before_scan_question_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("What should I do before my MRI?")
        )

    def test_generic_mri_mention_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("I have an MRI appointment tomorrow.")
        )

    def test_generic_after_mri_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("What happens after the MRI?")
        )

    def test_radiologist_mention_alone_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("The radiologist will review my scan.")
        )

    def test_results_question_with_after_scan_phrase(self):
        self.assertEqual(
            detect_temporal_intent(
                "When will I get my MRI results after the scan?"
            ),
            "results_followup",
        )

    def test_unrelated_report_mention_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("I need to report a problem with my appointment.")
        )

    def test_conflicting_results_and_discharge_intents_are_unknown(self):
        self.assertIsNone(
            detect_temporal_intent(
                "When will I get my results, and can I drive after the scan?"
            )
        )

    def test_generic_hinglish_after_mri_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("MRI ke baad kya hota hai?")
        )

    def test_generic_hinglish_after_scan_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent("Scan ke baad mujhe kya karna chahiye?")
        )

    def test_hinglish_results_question_after_scan(self):
        self.assertEqual(
            detect_temporal_intent("MRI ke baad report kab milegi?"),
            "results_followup",
        )

    def test_hinglish_explicit_discharge_after_scan(self):
        self.assertEqual(
            detect_temporal_intent("Scan ke baad main ghar ja sakta hoon?"),
            "post_scan_discharge",
        )


    def test_english_completed_mri_discharge_question(self):
        question = (
            "I have finished my MRI. What should I follow before leaving, "
            "especially if I received sedation?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "post_scan_discharge",
        )

    def test_english_results_contact_question(self):
        question = (
            "My MRI is complete. Whom should I ask about when and how "
            "I will get my results?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "results_followup",
        )

    def test_hindi_completed_mri_discharge_question(self):
        question = (
            "\u092e\u0947\u0930\u093e \u090f\u092e\u0906\u0930\u0906\u0908 "
            "\u0939\u094b \u0917\u092f\u093e \u0939\u0948\u0964 "
            "\u0935\u093f\u092d\u093e\u0917 \u0938\u0947 "
            "\u0928\u093f\u0915\u0932\u0928\u0947 \u0938\u0947 "
            "\u092a\u0939\u0932\u0947 \u092e\u0941\u091d\u0947 "
            "\u0915\u093f\u0928 \u0928\u093f\u0930\u094d\u0926\u0947\u0936\u094b\u0902 "
            "\u0915\u093e \u092a\u093e\u0932\u0928 \u0915\u0930\u0928\u093e "
            "\u091a\u093e\u0939\u093f\u090f, \u0916\u093e\u0938\u0915\u0930 "
            "\u0905\u0917\u0930 \u092e\u0941\u091d\u0947 "
            "\u092c\u0947\u0939\u094b\u0936 \u0915\u0930\u0928\u0947 "
            "\u0915\u0940 \u0926\u0935\u093e \u0926\u0940 "
            "\u0917\u0908 \u0925\u0940?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "post_scan_discharge",
        )

    def test_hinglish_completed_mri_discharge_question(self):
        question = (
            "Mera MRI complete ho gaya. Department se nikalne se pehle "
            "kya instructions follow karne hain, especially agar sedation di gayi thi?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "post_scan_discharge",
        )

    def test_hinglish_results_contact_question(self):
        question = (
            "MRI ho gaya hai. Results kab aur kaise milenge, "
            "ye kisse confirm karna chahiye?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "results_followup",
        )


    def test_unseen_english_discharge_paraphrase(self):
        self.assertEqual(
            detect_temporal_intent("The MRI is over. Can I go home now?"),
            "post_scan_discharge",
        )

    def test_unseen_english_sedation_discharge_paraphrase(self):
        self.assertEqual(
            detect_temporal_intent(
                "I completed the scan. Do I need someone to take me home "
                "after sedation?"
            ),
            "post_scan_discharge",
        )

    def test_unseen_english_results_contact_paraphrase(self):
        self.assertEqual(
            detect_temporal_intent(
                "Who can tell me when the scan report will be ready?"
            ),
            "results_followup",
        )

    def test_unseen_english_results_availability_paraphrase(self):
        self.assertEqual(
            detect_temporal_intent(
                "How long does it take for MRI findings to become available?"
            ),
            "results_followup",
        )

    def test_leaving_for_mri_is_not_post_scan(self):
        self.assertIsNone(
            detect_temporal_intent(
                "I am leaving for my MRI appointment now."
            )
        )

    def test_completed_mri_generic_question_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent(
                "My MRI is complete. What happens next?"
            )
        )

    def test_completed_mri_anxiety_mention_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent(
                "My MRI is complete, but I am still worried."
            )
        )

    def test_results_and_discharge_mixed_question_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent(
                "When will I get my results, and can I drive after the scan?"
            )
        )


    def test_unseen_hindi_discharge_paraphrase(self):
        question = (
            "\u090f\u092e\u0906\u0930\u0906\u0908 "
            "\u092a\u0942\u0930\u0940 \u0939\u094b \u0917\u0908 \u0939\u0948\u0964 "
            "\u0915\u094d\u092f\u093e \u0905\u092c \u092e\u0948\u0902 "
            "\u0918\u0930 \u091c\u093e \u0938\u0915\u0924\u093e \u0939\u0942\u0901?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "post_scan_discharge",
        )

    def test_unseen_hindi_results_availability(self):
        question = (
            "\u092e\u0947\u0930\u0940 \u090f\u092e\u0906\u0930\u0906\u0908 "
            "\u0915\u0940 \u0930\u093f\u092a\u094b\u0930\u094d\u091f "
            "\u0915\u092c \u0924\u0948\u092f\u093e\u0930 \u0939\u094b\u0917\u0940?"
        )
        self.assertEqual(
            detect_temporal_intent(question),
            "results_followup",
        )

    def test_unrelated_hindi_mri_completion_is_unknown(self):
        question = (
            "\u092e\u0947\u0930\u093e \u090f\u092e\u0906\u0930\u0906\u0908 "
            "\u0939\u094b \u0917\u092f\u093e\u0964 "
            "\u092e\u0948\u0902 \u0925\u0915\u093e \u0939\u0941\u0906 \u0939\u0942\u0901\u0964"
        )
        self.assertIsNone(detect_temporal_intent(question))

    def test_unseen_hinglish_discharge_paraphrase(self):
        self.assertEqual(
            detect_temporal_intent(
                "Scan khatam ho gaya. Kya main ab ghar ja sakta hoon?"
            ),
            "post_scan_discharge",
        )

    def test_unseen_hinglish_results_availability(self):
        self.assertEqual(
            detect_temporal_intent(
                "MRI report kitne din mein ready hogi?"
            ),
            "results_followup",
        )

    def test_unrelated_hinglish_mri_completion_is_unknown(self):
        self.assertIsNone(
            detect_temporal_intent(
                "Mera MRI ho gaya. Main abhi bhi thaka hua hoon."
            )
        )

    def test_empty_text_is_unknown(self):
        for question in ("", "   "):
            with self.subTest(question=question):
                self.assertIsNone(detect_temporal_intent(question))

    def test_non_string_input_is_rejected(self):
        for question in (None, 123):
            with self.subTest(question=question):
                with self.assertRaises(TypeError):
                    detect_temporal_intent(question)


    # TEMPORAL HOLDOUT REGRESSION TESTS

    def test_holdout_english_results_report_after_radiologist_review(self):
        self.assertEqual(
            detect_temporal_intent(
                "When will I receive the MRI report after the radiologist reviews it?"
            ),
            "results_followup",
        )

    def test_holdout_english_return_to_work_after_scan(self):
        self.assertEqual(
            detect_temporal_intent(
                "After my scan, can I return to work straight away?"
            ),
            "post_scan_discharge",
        )

    def test_holdout_english_drive_home_after_mri(self):
        self.assertEqual(
            detect_temporal_intent("Can I drive home after the MRI?"),
            "post_scan_discharge",
        )

    def test_holdout_english_completed_scan_go_home(self):
        self.assertEqual(
            detect_temporal_intent("I completed my scan. Can I go home now?"),
            "post_scan_discharge",
        )

    def test_holdout_hindi_during_janch(self):
        question = (
            "\u091c\u093e\u0902\u091a \u0915\u0947 \u0926\u094c\u0930\u093e\u0928 "
            "\u0915\u094d\u092f\u093e \u0915\u0930\u094d\u092e\u091a\u093e\u0930\u0940 "
            "\u092e\u0941\u091d\u0938\u0947 \u092c\u093e\u0924 \u0915\u0930 "
            "\u0938\u0915\u0924\u0947 \u0939\u0948\u0902?"
        )
        self.assertEqual(detect_temporal_intent(question), "during_scan")

    def test_holdout_hinglish_report_mujhe_kab_milegi(self):
        self.assertEqual(
            detect_temporal_intent("MRI report mujhe kab milegi?"),
            "results_followup",
        )

    def test_holdout_hinglish_findings_availability(self):
        self.assertEqual(
            detect_temporal_intent("Scan findings kab available hongi?"),
            "results_followup",
        )

    def test_holdout_hinglish_results_ready_contact_question(self):
        self.assertEqual(
            detect_temporal_intent(
                "Who can tell me ki MRI results kab ready honge?"
            ),
            "results_followup",
        )

    def test_holdout_hinglish_return_to_office_after_scan(self):
        self.assertEqual(
            detect_temporal_intent("Scan ke baad kya main office ja sakta hoon?"),
            "post_scan_discharge",
        )

    def test_holdout_hinglish_drive_home_after_mri(self):
        self.assertEqual(
            detect_temporal_intent("Can I drive home after my MRI?"),
            "post_scan_discharge",
        )

    def test_holdout_hinglish_leave_department_after_mri(self):
        self.assertEqual(
            detect_temporal_intent(
                "MRI complete ho gaya hai, kya main department se leave kar sakta hoon?"
            ),
            "post_scan_discharge",
        )
