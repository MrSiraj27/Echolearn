import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../core/voice_settings_state.dart';
import '../voice/device_voice_screen.dart';
import '../voice/voice_cloning_screen.dart';
import 'usage_screen.dart';

/// Mirrors the web app's Settings page: account actions, voice cloning, and
/// plan/usage — the same aggregation the web Settings screen does.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.graphic_eq),
            title: const Text('Voice Cloning'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const VoiceCloningScreen())),
          ),
          ListTile(
            leading: const Icon(Icons.record_voice_over),
            title: const Text('Device voice'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const DeviceVoiceScreen())),
          ),
          ListTile(
            leading: const Icon(Icons.bar_chart),
            title: const Text('Plan & usage'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const UsageScreen())),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Log out'),
            onTap: () {
              context.read<VoiceSettingsState>().resetForLogout();
              context.read<AuthState>().logout();
            },
          ),
        ],
      ),
    );
  }
}
