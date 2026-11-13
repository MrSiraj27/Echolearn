import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../core/voice_settings_state.dart';
import '../chat/chats_list_screen.dart';
import 'login_screen.dart';

/// Root of the app: tries to silently restore a session (like the web app's
/// on-load refresh), then shows Login or the Chats home depending on the result.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  // Captured once in initState — reading via `context.read` again in
  // dispose() is unsafe (the element tree may already be deactivated by
  // then), so the references are kept directly instead.
  late final AuthState _authState;
  late final VoiceSettingsState _voiceSettings;

  @override
  void initState() {
    super.initState();
    _authState = context.read<AuthState>();
    _voiceSettings = context.read<VoiceSettingsState>();
    _authState.addListener(_onAuthChanged);
    _authState.tryRestoreSession();
  }

  @override
  void dispose() {
    _authState.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (_authState.status == AuthStatus.authenticated) {
      _voiceSettings.load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = context.watch<AuthState>().status;
    switch (status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.authenticated:
        return const ChatsListScreen();
      case AuthStatus.unauthenticated:
        return const LoginScreen();
    }
  }
}
