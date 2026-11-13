import 'package:flutter/material.dart';

import 'login_screen.dart';

/// Mirrors the web app's post-signup "Check your email" screen. Verification
/// itself happens by tapping the link in the email, which opens the existing
/// web verify-email page (already deployed) — no in-app deep-linking needed
/// for v1, the user just comes back and logs in once verified.
class CheckEmailScreen extends StatelessWidget {
  final String email;

  const CheckEmailScreen({super.key, required this.email});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('Check your email',
                      style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 8),
                  const Text("We've sent you a verification link."),
                  const SizedBox(height: 12),
                  Text.rich(
                    TextSpan(
                      text: 'Click the link in the email we sent to ',
                      children: [
                        TextSpan(
                            text: email,
                            style:
                                const TextStyle(fontWeight: FontWeight.bold)),
                        const TextSpan(
                            text:
                                ' to activate your account, then come back and log in.'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: () => Navigator.of(context).pushAndRemoveUntil(
                        MaterialPageRoute(builder: (_) => const LoginScreen()),
                        (_) => false),
                    child: const Text('Back to login'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
