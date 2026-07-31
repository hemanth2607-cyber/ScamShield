import queue
import re
import math
import sys
import threading
import time
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import io
import speech_recognition as sr
import ctypes

# =====================================================================
# 1. SCAM NUMBER REGISTRY (Truecaller-Style Blacklist Simulator)
# =====================================================================
SCAM_NUMBER_DATABASE = {
    "+18008291040": "IRS Tax Fraud Impersonator",
    "+18009532134": "Tech Support Scam Center",
    "+14152345678": "Grandparent Jail Bail Extortionist",
    "+15125550199": "Robocall Utility Bill Thread"
}

def lookup_caller_id(phone_number):
    """
    Checks if the incoming number is flagged in the scam log databases.
    """
    clean_number = phone_number.replace(" ", "").replace("-", "")
    
    # Check absolute matches
    if clean_number in SCAM_NUMBER_DATABASE:
        return True, SCAM_NUMBER_DATABASE[clean_number]
        
    # Heuristics: Flag common high-risk spam prefixes (e.g., virtual VOIP numbers)
    if clean_number.startswith("+1888") or clean_number.startswith("+1877"):
        return True, "High-Risk VOIP Spam Range"
        
    return False, "Unknown Number (Clean Record)"

# =====================================================================
# 2. CORE MACHINE LEARNING MODEL
# =====================================================================
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

# =====================================================================
# 3. INTERVENTION MODULE
# =====================================================================
def trigger_hangup_alert(reason, transcribed_speech, source="Caller Database"):
    """
    Triggers an immediate modal window warning the user to hang up.
    """
    title = "🚨 HANG UP IMMEDIATELY - SCAM SHIELD 🚨"
    message = (
        f"CRITICAL WARNING: The system has flagged this call as dangerous!\n\n"
        f"Trigger Source: {source}\n"
        f"Threat Detected: {reason}\n"
        f"Heard on Line: \"{transcribed_speech}\"\n\n"
        f"RECOMMENDED ACTION: Click OK and hang up your phone immediately to prevent fraud."
    )
    # 0x10 = Hand/Stop Icon, 0x40000 = Topmost Window
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 | 0x40000)

# =====================================================================
# 4. LOW-LATENCY BACKGROUND STREAMER
# =====================================================================
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024  # Small buffers for immediate capture

audio_queue = queue.Queue()
recognizer = sr.Recognizer()
detector = NaiveBayesScamDetector()
detector.train(TRAINING_DATA)

# Threshold for Voice Activity Detection (VAD)
SILENCE_THRESHOLD = 300  
SPEECH_BUFFER = []

def audio_callback(indata, frames, time, status):
    """This function is called by sounddevice for each audio block."""
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def process_live_speech():
    """
    Monitors incoming raw audio buffers and processes speech segments 
    as soon as speaking pauses.
    """
    global SPEECH_BUFFER
    consecutive_silence = 0
    is_speaking = False

    while True:
        try:
            # Fetch small raw chunk from queue
            data_block = audio_queue.get(timeout=1)
            
            # Compute Volume Energy
            amplitude = np.abs(data_block).mean()
            
            if amplitude > SILENCE_THRESHOLD:
                SPEECH_BUFFER.append(data_block)
                consecutive_silence = 0
                is_speaking = True
            else:
                if is_speaking:
                    SPEECH_BUFFER.append(data_block)
                    consecutive_silence += 1
                    
                    # If silence lasts for ~1.5 seconds, process the phrase
                    if consecutive_silence > 22:  # 22 * 1024 frames roughly equals 1.4 seconds
                        full_phrase = np.concatenate(SPEECH_BUFFER, axis=0)
                        
                        # Clear buffer instantly for privacy/RAM clearance
                        SPEECH_BUFFER = []
                        is_speaking = False
                        consecutive_silence = 0
                        
                        # Convert raw array to text in memory
                        text = analyze_audio_chunk(full_phrase)
                        if text:
                            print(f"\n[Intercepted Line] \"{text}\"")
                            classification, confidence = detector.predict(text)
                            
                            if classification == "scam" and confidence > 0.60:
                                print(f"[CRITICAL THREAT] {classification.upper()} ({confidence:.2%})")
                                trigger_hangup_alert(f"Scam speech pattern matched ({confidence:.1%})", text, "Real-time AI analysis")
                            else:
                                print(f"[Safe] Confidence: {confidence:.2%}")
        except queue.Empty:
            continue

def analyze_audio_chunk(audio_array):
    """Transcribes raw NumPy arrays held in RAM."""
    byte_io = io.BytesIO()
    wav.write(byte_io, SAMPLE_RATE, audio_array)
    byte_io.seek(0)
    
    try:
        with sr.AudioFile(byte_io) as source:
            audio_record = recognizer.record(source)
            text = recognizer.recognize_google(audio_record)
            byte_io.close()
            return text
    except Exception:
        return None

# =====================================================================
# 5. EXECUTION ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    print("--- SCAM SHIELD SYSTEM START ---")
    
    # 1. Simulate Incoming Phone Call Number Check
    simulated_incoming_number = input("Simulate incoming Call Number (e.g., +18008291040 or press Enter for safe number): ")
    if not simulated_incoming_number.strip():
        simulated_incoming_number = "+15125550244"  # Simulated clean number
        
    print(f"\nIncoming Call: {simulated_incoming_number}")
    print("Checking Database logs...")
    
    is_scam, danger_reason = lookup_caller_id(simulated_incoming_number)
    if is_scam:
        print(f"\n[BLACKLIST ALERT] Caller ID matches flagged database records!")
        trigger_hangup_alert(f"Blacklisted Caller ID ({danger_reason})", "None (Call Blocked)", "Scam Number Database")
        print("System execution stopped. Call was terminated.")
        sys.exit(0)
    else:
        print(f"Caller Verified: {danger_reason}. Connection allowed.")

    # 2. Start Asynchronous Processing Thread
    processing_thread = threading.Thread(target=process_live_speech, daemon=True)
    processing_thread.start()

    # 3. Start Continuous Non-Blocking Audio Stream
    print("\nLive Call Monitor Active. Start speaking...")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, 
                        callback=audio_callback, blocksize=BLOCK_SIZE, 
                        dtype='int16'):
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nCall monitoring ended.")