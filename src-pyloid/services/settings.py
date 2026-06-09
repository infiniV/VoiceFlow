from dataclasses import dataclass
from typing import Literal, Optional
from .database import DatabaseService
from .hotkey import normalize_hotkey


# Whisper model options - all models supported by faster-whisper
# Order: multilingual models first, then English-only, then distilled
WHISPER_MODELS = [
    # Multilingual models (most commonly used)
    "tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo",
    # English-only models (optimized for English)
    "tiny.en", "base.en", "small.en", "medium.en",
    # Distilled models (faster inference, English-only)
    "distil-small.en", "distil-medium.en", "distil-large-v2", "distil-large-v3",
]

# Supported languages (subset - full list at https://github.com/openai/whisper)
WHISPER_LANGUAGES = [
    "auto",  # Auto-detect
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
    "zh", "ja", "ko", "ar", "hi", "tr", "vi", "th", "id"
]

# History retention options (in days, -1 = forever)
RETENTION_OPTIONS = {
    "7 days": 7,
    "30 days": 30,
    "90 days": 90,
    "Forever": -1,
}

# Theme palettes — aligned with VoiceKey (SimpleVoiceKeyboard iOS)
THEME_OPTIONS = ["midnight", "aurora", "ember", "ocean", "snowfall", "neonCity"]
LEGACY_THEME_MAP = {"dark": "midnight", "light": "snowfall", "system": "midnight"}

# Rewrite presets — aligned with iOS RewritePreset
REWRITE_PRESET_OPTIONS = ["grammar_correct", "professional", "casual_spoken", "concise"]


def normalize_theme(theme: str) -> str:
    mapped = LEGACY_THEME_MAP.get(theme, theme)
    return mapped if mapped in THEME_OPTIONS else "midnight"

# Device options for transcription
DEVICE_OPTIONS = ["auto", "cpu", "cuda"]


# LLM presets for meeting summarization. Order matches the UI radio group.
LLM_PRESETS = ["openai", "groq", "openrouter", "ollama", "custom"]

DEFAULT_LLM_PROMPT = (
    "You are a meeting-notes assistant. Read the transcript and produce a "
    "structured summary in Markdown with these sections, in this order:\n\n"
    "## TL;DR\nOne or two sentences.\n\n"
    "## Key topics\nBulleted list.\n\n"
    "## Decisions\nBulleted list.\n\n"
    "## Action items\nBulleted list. When an owner is mentioned, prefix with [Owner].\n\n"
    "## Open questions\nBulleted list. Omit the section if none.\n\n"
    "Transcript:\n{transcript}\n"
)


@dataclass
class Settings:
    language: str = "auto"
    model: str = "tiny"
    device: str = "auto"  # "auto", "cpu", or "cuda"
    auto_start: bool = True
    retention: int = -1  # days, -1 = forever
    theme: str = "midnight"
    auto_rewrite_enabled: bool = True
    rewrite_preset: str = "grammar_correct"
    filler_removal_enabled: bool = True
    onboarding_complete: bool = False
    microphone: int = -1  # -1 = default device, otherwise device id
    save_audio_to_history: bool = False
    # UI settings
    show_popup: bool = True  # Show/hide the floating recording indicator
    # Hotkey settings
    hold_hotkey: str = "ctrl+win"
    hold_hotkey_enabled: bool = True
    toggle_hotkey: str = "ctrl+shift+win"
    toggle_hotkey_enabled: bool = False
    # Transcription settings
    prepend_space: bool = False  # Add leading space before pasted text
    # Recordings (Meetings feature)
    recordings_mic_device: Optional[str] = None
    recordings_loopback_device: Optional[str] = None
    recordings_auto_transcribe: bool = True
    recordings_auto_summarize: bool = False
    recordings_auto_rename_title: bool = True
    # LLM config for summarization (API key stored separately via services.recording.secrets)
    llm_preset: str = "ollama"
    llm_endpoint: str = "http://localhost:11434/v1"
    llm_model: str = "llama3.2"
    llm_prompt_template: str = DEFAULT_LLM_PROMPT


class SettingsService:
    def __init__(self, db: DatabaseService):
        self.db = db
        self._cache: Optional[Settings] = None

    def get_settings(self) -> Settings:
        if self._cache:
            return self._cache

        settings = Settings(
            language=self.db.get_setting("language", "auto"),
            model=self.db.get_setting("model", "tiny"),
            device=self.db.get_setting("device", "auto"),
            auto_start=self.db.get_setting("auto_start", "true") == "true",
            retention=int(self.db.get_setting("retention", "-1")),
            theme=normalize_theme(self.db.get_setting("theme", "midnight")),
            auto_rewrite_enabled=self.db.get_setting("auto_rewrite_enabled", "true") == "true",
            rewrite_preset=self.db.get_setting("rewrite_preset", "grammar_correct"),
            filler_removal_enabled=self.db.get_setting("filler_removal_enabled", "true") == "true",
            onboarding_complete=self.db.get_setting("onboarding_complete", "false") == "true",
            microphone=int(self.db.get_setting("microphone", "-1")),
            save_audio_to_history=self.db.get_setting("save_audio_to_history", "false") == "true",
            # UI settings
            show_popup=self.db.get_setting("show_popup", "true") == "true",
            # Hotkey settings
            hold_hotkey=self.db.get_setting("hold_hotkey", "ctrl+win"),
            hold_hotkey_enabled=self.db.get_setting("hold_hotkey_enabled", "true") == "true",
            toggle_hotkey=self.db.get_setting("toggle_hotkey", "ctrl+shift+win"),
            toggle_hotkey_enabled=self.db.get_setting("toggle_hotkey_enabled", "false") == "true",
            # Transcription settings
            prepend_space=self.db.get_setting("prepend_space", "false") == "true",
            # Recordings (Meetings)
            recordings_mic_device=self.db.get_setting("recordings_mic_device", None),
            recordings_loopback_device=self.db.get_setting("recordings_loopback_device", None),
            recordings_auto_transcribe=self.db.get_setting("recordings_auto_transcribe", "true") == "true",
            recordings_auto_summarize=self.db.get_setting("recordings_auto_summarize", "false") == "true",
            recordings_auto_rename_title=self.db.get_setting("recordings_auto_rename_title", "true") == "true",
            # LLM config
            llm_preset=self.db.get_setting("llm_preset", "ollama"),
            llm_endpoint=self.db.get_setting("llm_endpoint", "http://localhost:11434/v1"),
            llm_model=self.db.get_setting("llm_model", "llama3.2"),
            llm_prompt_template=self.db.get_setting("llm_prompt_template", DEFAULT_LLM_PROMPT),
        )
        self._cache = settings
        return settings

    def update_settings(
        self,
        *,
        language: Optional[str] = None,
        model: Optional[str] = None,
        device: Optional[str] = None,
        auto_start: Optional[bool] = None,
        retention: Optional[int] = None,
        theme: Optional[str] = None,
        auto_rewrite_enabled: Optional[bool] = None,
        rewrite_preset: Optional[str] = None,
        filler_removal_enabled: Optional[bool] = None,
        onboarding_complete: Optional[bool] = None,
        microphone: Optional[int] = None,
        save_audio_to_history: Optional[bool] = None,
        hold_hotkey: Optional[str] = None,
        hold_hotkey_enabled: Optional[bool] = None,
        toggle_hotkey: Optional[str] = None,
        toggle_hotkey_enabled: Optional[bool] = None,
        show_popup: Optional[bool] = None,
        prepend_space: Optional[bool] = None,
        # Recordings
        recordings_mic_device: Optional[str] = None,
        recordings_loopback_device: Optional[str] = None,
        recordings_auto_transcribe: Optional[bool] = None,
        recordings_auto_summarize: Optional[bool] = None,
        recordings_auto_rename_title: Optional[bool] = None,
        # LLM
        llm_preset: Optional[str] = None,
        llm_endpoint: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_prompt_template: Optional[str] = None,
    ) -> Settings:
        if language is not None:
            self.db.set_setting("language", language)
        if model is not None:
            self.db.set_setting("model", model)
        if device is not None:
            self.db.set_setting("device", device)
        if auto_start is not None:
            self.db.set_setting("auto_start", "true" if auto_start else "false")
        if retention is not None:
            self.db.set_setting("retention", str(retention))
        if theme is not None:
            self.db.set_setting("theme", normalize_theme(theme))
        if auto_rewrite_enabled is not None:
            self.db.set_setting("auto_rewrite_enabled", "true" if auto_rewrite_enabled else "false")
        if rewrite_preset is not None:
            self.db.set_setting("rewrite_preset", rewrite_preset)
        if filler_removal_enabled is not None:
            self.db.set_setting("filler_removal_enabled", "true" if filler_removal_enabled else "false")
        if onboarding_complete is not None:
            self.db.set_setting("onboarding_complete", "true" if onboarding_complete else "false")
        if microphone is not None:
            self.db.set_setting("microphone", str(microphone))
        if save_audio_to_history is not None:
            self.db.set_setting("save_audio_to_history", "true" if save_audio_to_history else "false")
        if show_popup is not None:
            self.db.set_setting("show_popup", "true" if show_popup else "false")
        if prepend_space is not None:
            self.db.set_setting("prepend_space", "true" if prepend_space else "false")
        # Hotkey settings - normalize before storing for consistent format
        if hold_hotkey is not None:
            self.db.set_setting("hold_hotkey", normalize_hotkey(hold_hotkey))
        if hold_hotkey_enabled is not None:
            self.db.set_setting("hold_hotkey_enabled", "true" if hold_hotkey_enabled else "false")
        if toggle_hotkey is not None:
            self.db.set_setting("toggle_hotkey", normalize_hotkey(toggle_hotkey))
        if toggle_hotkey_enabled is not None:
            self.db.set_setting("toggle_hotkey_enabled", "true" if toggle_hotkey_enabled else "false")
        # Recordings (Meetings)
        if recordings_mic_device is not None:
            self.db.set_setting("recordings_mic_device", recordings_mic_device)
        if recordings_loopback_device is not None:
            self.db.set_setting("recordings_loopback_device", recordings_loopback_device)
        if recordings_auto_transcribe is not None:
            self.db.set_setting("recordings_auto_transcribe", "true" if recordings_auto_transcribe else "false")
        if recordings_auto_summarize is not None:
            self.db.set_setting("recordings_auto_summarize", "true" if recordings_auto_summarize else "false")
        if recordings_auto_rename_title is not None:
            self.db.set_setting("recordings_auto_rename_title", "true" if recordings_auto_rename_title else "false")
        # LLM config
        if llm_preset is not None:
            self.db.set_setting("llm_preset", llm_preset)
        if llm_endpoint is not None:
            self.db.set_setting("llm_endpoint", llm_endpoint)
        if llm_model is not None:
            self.db.set_setting("llm_model", llm_model)
        if llm_prompt_template is not None:
            self.db.set_setting("llm_prompt_template", llm_prompt_template)

        self._cache = None  # Invalidate cache
        return self.get_settings()

    def get_available_models(self) -> list:
        return WHISPER_MODELS

    def get_available_languages(self) -> list:
        return WHISPER_LANGUAGES

    def get_retention_options(self) -> dict:
        return RETENTION_OPTIONS

    def get_theme_options(self) -> list:
        return THEME_OPTIONS

    def get_device_options(self) -> list:
        return DEVICE_OPTIONS
