"""
app/constants.py
─────────────────
Shared constants used across the chatbot application.

YES_WORDS / NO_WORDS:
    Used in WebSocket handler to interpret user confirmation replies
    for two-step table flow and audio transcription confirmation.
"""

YES_WORDS = {
    "yes", "yeah", "yep", "yup", "ya", "y",
    "correct", "right", "true", "exactly", "give me",
    "ok", "okay", "okey", "k", "kk", "kkkk",
    "sure", "surely", "of course",
    "confirmed", "confirm", "confirmation",
    "proceed", "go ahead", "continue",
    "please proceed", "you can proceed",
    "yes please", "go on", "carry on",
    "that's right", "thats right",
    "yes that's correct", "yes thats correct",
    "sounds good", "looks good", "all good",
    "fine", "works", "works for me",
    "perfect", "great", "nice",
    "yess", "yea", "yaah", "yup yup",
    "indeed", "absolutely", "definitely",
    "affirmative", "roger", "approved",
    "do it", "let's go", "lets go",
}

NO_WORDS = {
    "no", "nope", "nah", "n",
    "wrong", "incorrect", "not correct", "not right",
    "that's wrong", "thats wrong",
    "no that's wrong", "no thats wrong",
    "not really", "not exactly",
    "don't", "do not", "dont",
    "stop", "hold on", "wait",
    "cancel", "abort", "skip",
    "no thanks", "no thank you",
    "negative", "decline", "rejected",
    "not good", "bad", "doesn't work", "doesnt work",
    "not fine", "not okay", "not ok",
    "change it", "modify", "edit this",
    "try again", "redo", "recheck",
    "nah bro", "no way", "never",
    "i disagree", "disagree", "not agreed",
}

# Max audio payload size (500 KB)
MAX_AUDIO_BYTES = 500 * 1024