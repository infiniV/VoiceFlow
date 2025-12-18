
import { Lock, Gauge, Wand2 } from "lucide-react";

export const APP_VERSION = "1.2.1";

export const THEME_OPTIONS = [
  { val: 'light', label: 'Light' },
  { val: 'dark', label: 'Dark' },
  { val: 'system', label: 'System' },
] as const;

// All models supported by faster-whisper with descriptions
// Organized by category for better UX
export const MODEL_OPTIONS = [
  // === Multilingual Models (support 99+ languages) ===
  {
    id: 'tiny', label: 'Tiny', desc: 'Fastest', detail: '39M params',
    tradeoff: 'Basic accuracy, good for testing', category: 'multilingual',
    speed: 5, accuracy: 1, size: '~75 MB',
    bestFor: 'Quick tests, low-resource devices, real-time previews',
    description: 'The smallest and fastest model. Great for testing your setup or when speed is critical. Supports 99+ languages but with limited accuracy.',
  },
  {
    id: 'base', label: 'Base', desc: 'Fast', detail: '74M params',
    tradeoff: 'Good for simple/clear audio', category: 'multilingual',
    speed: 4, accuracy: 2, size: '~145 MB',
    bestFor: 'Clear audio, simple vocabulary, quick transcriptions',
    description: 'A step up from Tiny with noticeably better accuracy while remaining fast. Works well with clear audio and common vocabulary.',
  },
  {
    id: 'small', label: 'Small', desc: 'Balanced', detail: '244M params',
    tradeoff: 'Good accuracy, reasonable speed', category: 'multilingual',
    speed: 3, accuracy: 3, size: '~466 MB',
    bestFor: 'General use, meetings, interviews, podcasts',
    description: 'The sweet spot for most users. Offers good accuracy across various accents and audio conditions while maintaining reasonable speed.',
  },
  {
    id: 'medium', label: 'Medium', desc: 'Accurate', detail: '769M params',
    tradeoff: 'High quality, slower', category: 'multilingual',
    speed: 2, accuracy: 4, size: '~1.5 GB',
    bestFor: 'Professional transcription, accented speech, noisy audio',
    description: 'High-quality transcription suitable for professional use. Handles accents, technical terminology, and challenging audio well.',
  },
  {
    id: 'large-v1', label: 'Large v1', desc: 'Very Accurate', detail: '1.5B params',
    tradeoff: 'Original large model', category: 'multilingual',
    speed: 1, accuracy: 4, size: '~3.1 GB',
    bestFor: 'Maximum accuracy needs, archival transcription',
    description: 'The original large model. Very accurate but slower. Consider v2 or v3 for better performance.',
  },
  {
    id: 'large-v2', label: 'Large v2', desc: 'Very Accurate', detail: '1.5B params',
    tradeoff: 'Improved over v1', category: 'multilingual',
    speed: 1, accuracy: 5, size: '~3.1 GB',
    bestFor: 'Professional/medical/legal transcription, rare languages',
    description: 'Improved version with better accuracy across all languages. Recommended over v1 for most use cases requiring maximum accuracy.',
  },
  {
    id: 'large-v3', label: 'Large v3', desc: 'Most Accurate', detail: '1.5B params',
    tradeoff: 'Best quality, slowest', category: 'multilingual',
    speed: 1, accuracy: 5, size: '~3.1 GB',
    bestFor: 'Critical accuracy, difficult audio, rare languages',
    description: 'The most accurate model available. Best for critical transcription where accuracy is paramount. Supports 99+ languages with state-of-the-art quality.',
  },
  {
    id: 'turbo', label: 'Turbo', desc: 'Fast + Accurate', detail: '809M params',
    tradeoff: 'Best speed/quality balance', category: 'multilingual',
    speed: 4, accuracy: 4, size: '~1.6 GB',
    bestFor: 'Daily use, real-time transcription, productivity',
    description: 'The recommended model for most users. Combines near large-model accuracy with much faster speed. Excellent for daily dictation and productivity.',
  },

  // === English-Only Models (optimized for English, slightly faster) ===
  {
    id: 'tiny.en', label: 'Tiny (EN)', desc: 'Fastest English', detail: '39M params',
    tradeoff: 'English only, basic accuracy', category: 'english',
    speed: 5, accuracy: 2, size: '~75 MB',
    bestFor: 'English-only quick tests, minimal resources',
    description: 'Optimized specifically for English. Slightly better English accuracy than multilingual Tiny, with the same fast speed.',
  },
  {
    id: 'base.en', label: 'Base (EN)', desc: 'Fast English', detail: '74M params',
    tradeoff: 'English only, good for clear audio', category: 'english',
    speed: 4, accuracy: 2, size: '~145 MB',
    bestFor: 'English podcasts, clear speech, casual use',
    description: 'English-optimized Base model. Better English recognition than the multilingual version with similar speed characteristics.',
  },
  {
    id: 'small.en', label: 'Small (EN)', desc: 'Balanced English', detail: '244M params',
    tradeoff: 'English only, good accuracy', category: 'english',
    speed: 3, accuracy: 4, size: '~466 MB',
    bestFor: 'English meetings, interviews, general dictation',
    description: 'Great balance of speed and accuracy for English. Handles various American and British accents well.',
  },
  {
    id: 'medium.en', label: 'Medium (EN)', desc: 'Accurate English', detail: '769M params',
    tradeoff: 'English only, high quality', category: 'english',
    speed: 2, accuracy: 5, size: '~1.5 GB',
    bestFor: 'Professional English transcription, accented English',
    description: 'High-accuracy English model. Excellent for professional transcription, technical content, and various English accents.',
  },

  // === Distilled Models (faster inference, English-only, knowledge distillation) ===
  {
    id: 'distil-small.en', label: 'Distil Small', desc: 'Fast Distilled', detail: '166M params',
    tradeoff: 'English only, 6x faster than small', category: 'distilled',
    speed: 5, accuracy: 3, size: '~332 MB',
    bestFor: 'Fast English transcription, real-time use',
    description: 'Distilled from larger models using knowledge distillation. 6x faster than Small with similar accuracy. Great for real-time English transcription.',
  },
  {
    id: 'distil-medium.en', label: 'Distil Medium', desc: 'Balanced Distilled', detail: '394M params',
    tradeoff: 'English only, faster than medium', category: 'distilled',
    speed: 4, accuracy: 4, size: '~756 MB',
    bestFor: 'Quality English transcription with good speed',
    description: 'Balanced distilled model offering good accuracy at improved speeds. Excellent choice for English-only workflows.',
  },
  {
    id: 'distil-large-v2', label: 'Distil Large v2', desc: 'Fast + Accurate', detail: '756M params',
    tradeoff: 'English only, 6x faster than large', category: 'distilled',
    speed: 4, accuracy: 5, size: '~1.5 GB',
    bestFor: 'Professional English, speed + accuracy balance',
    description: 'Distilled from Large-v2. Achieves 6x speedup while maintaining most of the accuracy. Excellent for professional English transcription.',
  },
  {
    id: 'distil-large-v3', label: 'Distil Large v3', desc: 'Best Distilled', detail: '756M params',
    tradeoff: 'English only, near large-v3 quality', category: 'distilled',
    speed: 4, accuracy: 5, size: '~1.5 GB',
    bestFor: 'Best English accuracy with reasonable speed',
    description: 'The best distilled model. Near large-v3 accuracy at significantly faster speeds. Highly recommended for English-only professional use.',
  },
] as const;

// Model category descriptions for UI grouping
export const MODEL_CATEGORIES = {
  multilingual: { label: 'Multilingual', desc: 'Supports 99+ languages', color: 'text-blue-400' },
  english: { label: 'English Only', desc: 'Optimized for English', color: 'text-amber-400' },
  distilled: { label: 'Distilled', desc: 'Faster inference, English-only', color: 'text-purple-400' },
} as const;

// Helper to check if model is English-only
export const isEnglishOnlyModel = (modelId: string) =>
  modelId.endsWith('.en') || modelId.startsWith('distil-');

export const ONBOARDING_FEATURES = [
  { icon: Lock, label: "100% Local", desc: "Never leaves your device" },
  { icon: Gauge, label: "Lightning Fast", desc: "Real-time transcription" },
  { icon: Wand2, label: "AI Powered", desc: "State-of-the-art accuracy" },
];
