import os
import re
import math
import ctypes
import speech_recognition as sr

TRAINING_DATA = [
    ("This is the IRS, you owe back taxes and will be arrested", "scam"),
    ("Your bank account is compromised, send money to the secure vault", "scam"),
    ("Congratulations, you won a free gift card, click here or call us", "scam"),
    ("This is Microsoft support, your computer has a virus, download this link", "scam"),
    ("Your grandson is in jail and needs bail money immediately", "scam"),
    ("Urgent: Pay your utility bill now or we will shut off your electricity", "scam"),
    ("Verify your social security number to avoid immediate suspension", "scam"),
    ("Send bitcoin to unlock your locked bank account", "scam"),
    
    ("Hey grandma, are we still meeting for lunch tomorrow at twelve", "safe"),
    ("Your dentist appointment is scheduled for Tuesday at three PM", "safe"),
    ("Hi, I am calling from the library, your book is ready for pickup", "safe"),
    ("Did you see the weather forecast for this weekend? It looks like rain", "safe"),
    ("Hey, I left my keys at your house, can I come by to get them", "safe"),
    ("The package you ordered yesterday has been delivered to your porch", "safe"),
    ("Hi, this is mom, just calling to check in and see how you are doing", "safe"),
    ("Your prescription is ready for pickup at the local pharmacy", "safe")
]

class NaiveBayesScamDetector:
    def __init__(self):
        self.scam_word_counts = {}
        self.safe_word_counts = {}
        self.total_scam_words = 0
        self.total_safe_words = 0
        self.num_scam_docs = 0
        self.num_safe_docs = 0
        self.unique_words = set()

    def _tokenize(self, text):
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        return words

    def train(self, dataset):
        for text, label in dataset:
            words = self._tokenize(text)
            if label == "scam":
                self.num_scam_docs += 1
                for word in words:
                    self.scam_word_counts[word] = self.scam_word_counts.get(word, 0) + 1
                    self.total_scam_words += 1
                    self.unique_words.add(word)
            elif label == "safe":
                self.num_safe_docs += 1
                for word in words:
                    self.safe_word_counts[word] = self.safe_word_counts.get(word, 0) + 1
                    self.total_safe_words += 1
                    self.unique_words.add(word)

    def predict(self, text):
        words = self._tokenize(text)
        total_docs = self.num_scam_docs + self.num_safe_docs
        
        if total_docs == 0:
            return "safe", 0.5
            
        p_scam_log = math.log(self.num_scam_docs / total_docs)
        p_safe_log = math.log(self.num_safe_docs / total_docs)
        vocabulary_size = len(self.unique_words)

        for word in words:
            scam_word_count = self.scam_word_counts.get(word, 0)
            p_word_given_scam = (scam_word_count + 1) / (self.total_scam_words + vocabulary_size)
            p_scam_log += math.log(p_word_given_scam)

            safe_word_count = self.safe_word_counts.get(word, 0)
            p_word_given_safe = (safe_word_count + 1) / (self.total_safe_words + vocabulary_size)
            p_safe_log += math.log(p_word_given_safe)

        max_log = max(p_scam_log, p_safe_log)
        prob_scam_raw = math.exp(p_scam_log - max_log)
        prob_safe_raw = math.exp(p_safe_log - max_log)
        
        sum_raw = prob_scam_raw + prob_safe_raw
        final_scam_prob = prob_scam_raw / sum_raw

        if final_scam_prob > 0.5:
            return "scam", final_scam_prob
        else:
            return "safe", (1 - final_scam_prob)

def transcribe_audio_file(file_path):
    recognizer = sr.Recognizer()
    if not os.path.exists(file_path):
        return None
    with sr.AudioFile(file_path) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data)
            return text
        except Exception:
            return None

def trigger_user_warning(scam_type, confidence, transcribed_text):
    title = "⚠️ SCAM SHIELD WARNING ⚠️"
    message = (
        f"Warning: This call appears to be a fraudulent scam!\n\n"
        f"Detected Tactic: High probability of {scam_type.upper()} ({confidence:.1%} certainty).\n"
        f"Transcribed Text: \"{transcribed_text}\"\n\n"
        f"ACTION ADVISED: Hang up immediately."
    )
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 | 0x40000)

def notify_caregiver(scam_type, confidence, transcribed_text):
    log_file_path = "caregiver_alerts.log"
    alert_message = (
        f"--- CAREGIVER EMERGENCY ALERT ---\n"
        f"Status: Active call flagged as SCAM.\n"
        f"Details: Classified as '{scam_type}' with {confidence:.2%} confidence.\n"
        f"Intercepted speech: \"{transcribed_text}\"\n"
        f"---------------------------------\n\n"
    )
    with open(log_file_path, "a") as log_file:
        log_file.write(alert_message)

if __name__ == "__main__":
    detector = NaiveBayesScamDetector()
    detector.train(TRAINING_DATA)
    test_file = "test_scam_call.wav"
    transcribed_text = transcribe_audio_file(test_file)
    
    if transcribed_text:
        classification, confidence = detector.predict(transcribed_text)
        if classification == "scam" and confidence > 0.60:
            notify_caregiver("Urgent demand / Impersonation", confidence, transcribed_text)
            trigger_user_warning("Urgent demand / Impersonation", confidence, transcribed_text)
    else:
        # Text simulation backup
        test_phrase = "Hello, your bank account is compromised. Send money to the secure vault immediately."
        classification, confidence = detector.predict(test_phrase)
        if classification == "scam" and confidence > 0.60:
            notify_caregiver("Bank Impersonation", confidence, test_phrase)
            trigger_user_warning("Bank Impersonation", confidence, test_phrase)
