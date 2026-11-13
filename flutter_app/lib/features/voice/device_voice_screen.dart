import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/voice_settings_state.dart';

/// Mobile equivalent of the web app's browser-voice picker (Settings ->
/// choose which SpeechSynthesis voice reads answers when no server/cloned
/// voice is used). Here it's the device's installed TTS voices instead.
class DeviceVoiceScreen extends StatelessWidget {
  const DeviceVoiceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final voiceSettings = context.watch<VoiceSettingsState>();

    return Scaffold(
      appBar: AppBar(title: const Text('Device voice')),
      body: voiceSettings.deviceVoices.isEmpty
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                    'No selectable voices were found on this device — the system default will be used.'),
              ),
            )
          : ListView.builder(
              itemCount: voiceSettings.deviceVoices.length,
              itemBuilder: (context, i) {
                final voice = voiceSettings.deviceVoices[i];
                final selected = voice['name'] == voiceSettings.deviceVoiceName;
                return RadioListTile<String>(
                  title: Text(voice['name'] ?? 'Unknown'),
                  subtitle: Text(voice['locale'] ?? ''),
                  value: voice['name'] ?? '',
                  groupValue: voiceSettings.deviceVoiceName,
                  selected: selected,
                  onChanged: (_) => voiceSettings.setDeviceVoice(voice),
                );
              },
            ),
    );
  }
}
