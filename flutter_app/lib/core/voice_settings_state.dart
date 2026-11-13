import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/voice_service.dart';

const _devicePrefsKey = 'device_voice_name';

/// Mirrors frontend/lib/speech-context.tsx: whether the user has a voice
/// sample uploaded, whether "My Voice" (cloning) is on, and which on-device
/// voice to use as the fallback/default (the mobile equivalent of the web
/// app's browser SpeechSynthesis voice picker) — persisted the same way the
/// web app persists it to localStorage, just with SharedPreferences instead.
class VoiceSettingsState extends ChangeNotifier {
  final VoiceService service;
  final FlutterTts _tts = FlutterTts();

  bool hasVoiceSample = false;
  bool useMyVoice = false;
  bool loaded = false;

  List<Map<String, String>> deviceVoices = [];
  String? deviceVoiceName;

  VoiceSettingsState(this.service);

  Future<void> load() async {
    await Future.wait([_loadSampleInfo(), _loadDeviceVoices()]);
    loaded = true;
    notifyListeners();
  }

  Future<void> _loadSampleInfo() async {
    try {
      final info = await service.sampleInfo();
      hasVoiceSample = info['has_sample'] as bool? ?? false;
    } catch (_) {}
  }

  Future<void> _loadDeviceVoices() async {
    try {
      final raw = await _tts.getVoices;
      deviceVoices = (raw as List)
          .map((v) => (v as Map)
              .map((key, value) => MapEntry(key.toString(), value.toString())))
          .where((v) => (v['locale'] ?? '').toLowerCase().startsWith('en'))
          .toList();

      final prefs = await SharedPreferences.getInstance();
      deviceVoiceName = prefs.getString(_devicePrefsKey);
      if (deviceVoiceName != null) {
        final match = deviceVoices
            .firstWhere((v) => v['name'] == deviceVoiceName, orElse: () => {});
        if (match.isNotEmpty)
          await _tts
              .setVoice({'name': match['name']!, 'locale': match['locale']!});
      }
    } catch (_) {
      // Voice enumeration isn't supported on every platform — device TTS still
      // works with the system default, it just can't be picked explicitly.
    }
  }

  Future<void> setDeviceVoice(Map<String, String> voice) async {
    deviceVoiceName = voice['name'];
    await _tts.setVoice({'name': voice['name']!, 'locale': voice['locale']!});
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_devicePrefsKey, voice['name']!);
    notifyListeners();
  }

  void setUseMyVoice(bool value) {
    useMyVoice = value;
    notifyListeners();
  }

  void setHasVoiceSample(bool value) {
    hasVoiceSample = value;
    if (!value) useMyVoice = false;
    notifyListeners();
  }

  /// Called on logout — clears the previous user's voice-sample/cloning state
  /// so it doesn't leak into whichever account logs in next on this device.
  /// Device voice choice is left alone: it's a device preference, not
  /// account data.
  void resetForLogout() {
    hasVoiceSample = false;
    useMyVoice = false;
    loaded = false;
    notifyListeners();
  }
}
