import json
from pathlib import Path

path = Path("chatbot/evaluation/multilingual_dev_questions.json")

with path.open("r", encoding="utf-8") as f:
    records = json.load(f)

# Replace only the 20 Hindi retrieval questions.
hindi_questions = {
    "DEVHI001": "मेरी कोलोनोस्कोपी होने वाली है। मैं कई नियमित दवाइयाँ लेता हूँ। इनके बारे में डॉक्टर या टीम को क्या बताना चाहिए?",
    "DEVHI002": "कोलोनोस्कोपी से पहले मेरी दवाओं की सूची किससे जाँच करवानी चाहिए? क्या कोई दवा खुद बंद करनी चाहिए?",
    "DEVHI003": "कोलोनोस्कोपी से पहले गलती से तय समय के बाद कुछ खा लिया। अब मुझे किससे संपर्क करना चाहिए?",
    "DEVHI004": "मेरी कोलोनोस्कोपी के लिए ठोस खाना और तरल पदार्थ कब बंद करने हैं, इसका सही समय कहाँ से पता चलेगा?",
    "DEVHI005": "CT स्कैन के दिन क्या धातु वाली ज़िप या बटन के बिना कपड़े पहनना बेहतर होगा?",
    "DEVHI006": "CT स्कैन से पहले मेरी कोई धातु की चीज़ नहीं निकल रही है। क्या मुझे स्टाफ से मदद माँगनी चाहिए?",
    "DEVHI007": "क्या हर CT स्कैन में खाने से पहले उपवास करना ज़रूरी होता है, या निर्देश अलग हो सकते हैं?",
    "DEVHI008": "CT स्कैन से पहले उपवास का निर्देश मिला है और मुझे डायबिटीज़ भी है। दवाओं के बारे में किससे पूछूँ?",
    "DEVHI009": "ECG कराने से पहले क्या मुझे स्टाफ को अपने पेसमेकर के बारे में बताना चाहिए?",
    "DEVHI010": "मेरे शरीर में दिल से जुड़ा एक इम्प्लांटेड उपकरण है। ECG टीम को इसकी जानकारी देना क्यों ज़रूरी है?",
    "DEVHI011": "ECG से पहले मैंने छाती पर तेल लगाया है। क्या इलेक्ट्रोड लगाने से पहले यह बात स्टाफ को बतानी चाहिए?",
    "DEVHI012": "ECG के लिए त्वचा तैयार करने के नाम पर क्या मुझे घर पर ही छाती के बाल शेव करने चाहिए?",
    "DEVHI013": "X-ray से पहले अगर गर्भवती होने की थोड़ी भी संभावना हो तो क्या रेडियोग्राफर को बताना चाहिए?",
    "DEVHI014": "मुझे अभी गर्भावस्था की पुष्टि नहीं हुई है। क्या X-ray विभाग को अपनी आशंका बताना ज़रूरी है?",
    "DEVHI015": "X-ray के समय शरीर पर पहनी किन चीज़ों को हटाने के लिए कहा जा सकता है?",
    "DEVHI016": "मेरे पास धातु वाला एक हटाया जा सकने वाला उपकरण है। X-ray से पहले इसे लेकर किससे सलाह लूँ?",
    "DEVHI017": "मेरे कान में कोक्लियर इम्प्लांट है। MRI से पहले इसकी सुरक्षा की जाँच कौन करेगा?",
    "DEVHI018": "मेरे पुराने ऑपरेशन में धातु का इम्प्लांट लगाया गया था। MRI से पहले टीम को क्या जानकारी देनी चाहिए?",
    "DEVHI019": "MRI के दौरान क्या मोबाइल और स्मार्टवॉच जैसी इलेक्ट्रॉनिक चीज़ें अपने पास रख सकते हैं?",
    "DEVHI020": "मेरे कपड़ों में धातु के हिस्से हैं। MRI के लिए कपड़े बदलने से पहले किससे निर्देश लेने चाहिए?",
}

expected_ids = {
    f"DEVHI{i:03d}" for i in range(1, 21)
}

actual_ids = {
    r["id"] for r in records
    if r["language"] == "hi" and r["expected_action"] == "retrieve_step"
}

assert actual_ids == expected_ids, (
    f"Unexpected Hindi retrieval IDs. "
    f"Missing: {expected_ids - actual_ids}; "
    f"Extra: {actual_ids - expected_ids}"
)

# Preserve a snapshot of all records that must not change.
untouched_before = {
    r["id"]: r.copy()
    for r in records
    if r["id"] not in expected_ids
}

for record in records:
    if record["id"] in hindi_questions:
        record["question"] = hindi_questions[record["id"]]

# Validate every repaired question.
for record in records:
    if record["id"] in expected_ids:
        question = record["question"]
        assert any("\u0900" <= c <= "\u097f" for c in question), (
            f"Missing Devanagari text: {record['id']}"
        )
        assert question.strip(), f"Empty question: {record['id']}"

# Verify all other records are unchanged.
untouched_after = {
    r["id"]: r.copy()
    for r in records
    if r["id"] not in expected_ids
}
assert untouched_before == untouched_after, "An unrelated record changed"

# Write clean UTF-8 JSON.
path.write_text(
    json.dumps(records, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

# Reopen from disk and verify persisted Unicode.
with path.open("r", encoding="utf-8") as f:
    saved = json.load(f)

for record in saved:
    if record["id"] in expected_ids:
        assert any(
            "\u0900" <= c <= "\u097f"
            for c in record["question"]
        )

print("Hindi development questions repaired successfully.")
print("Repaired Hindi retrieval questions:", len(expected_ids))
print("Other records preserved:", len(untouched_after))
print("Total records:", len(saved))
print("UTF-8 persistence check: PASSED")
print("\nSample repaired questions:")
for record in saved:
    if record["id"] in ("DEVHI001", "DEVHI017"):
        print(record["id"] + ":", record["question"])
