import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/api_client.dart';
import 'core/app_config.dart';
import 'core/app_theme.dart';
import 'core/auth_state.dart';
import 'core/token_store.dart';
import 'core/voice_settings_state.dart';
import 'features/auth/auth_gate.dart';
import 'services/voice_service.dart';

void main() {
  // Required before touching any platform channel — VoiceSettingsState's
  // FlutterTts() is constructed right below, before runApp() would otherwise
  // have initialized the binding itself.
  WidgetsFlutterBinding.ensureInitialized();

  final tokenStore = TokenStore();
  final apiClient = ApiClient(baseUrl: apiBaseUrl, tokenStore: tokenStore);
  final authState = AuthState(api: apiClient, tokenStore: tokenStore);
  final voiceSettings = VoiceSettingsState(VoiceService(apiClient));

  runApp(EchoLearnApp(authState: authState, voiceSettings: voiceSettings));
}

class EchoLearnApp extends StatelessWidget {
  final AuthState authState;
  final VoiceSettingsState voiceSettings;

  const EchoLearnApp({super.key, required this.authState, required this.voiceSettings});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: authState),
        ChangeNotifierProvider.value(value: voiceSettings),
      ],
      child: MaterialApp(
        title: 'EchoLearn',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        darkTheme: AppTheme.dark,
        home: const AuthGate(),
      ),
    );
  }
}
