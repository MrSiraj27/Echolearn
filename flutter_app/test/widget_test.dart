import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:echolearn_app/core/api_client.dart';
import 'package:echolearn_app/core/auth_state.dart';
import 'package:echolearn_app/core/token_store.dart';
import 'package:echolearn_app/core/voice_settings_state.dart';
import 'package:echolearn_app/main.dart';
import 'package:echolearn_app/services/voice_service.dart';

void main() {
  testWidgets('App boots and shows a loading state while restoring the session', (WidgetTester tester) async {
    final tokenStore = TokenStore();
    final apiClient = ApiClient(baseUrl: 'https://example.invalid', tokenStore: tokenStore);
    final authState = AuthState(api: apiClient, tokenStore: tokenStore);
    final voiceSettings = VoiceSettingsState(VoiceService(apiClient));

    await tester.pumpWidget(EchoLearnApp(authState: authState, voiceSettings: voiceSettings));

    // AuthGate kicks off tryRestoreSession() (async network + secure-storage
    // calls) in initState — a single pump (no network round trip completed
    // yet) should still show the loading spinner, not crash.
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
