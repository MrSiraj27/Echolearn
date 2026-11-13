import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import 'forgot_password_screen.dart';
import 'signup_screen.dart';

/// Mirrors frontend/app/(auth)/login/page.tsx: email/password form, and when
/// login fails with the "please verify your email" message, an inline
/// "Resend verification email" action — same UX as the web app.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  bool _loading = false;
  bool _resendLoading = false;
  String? _error;
  String? _resendMessage;
  bool _needsVerification = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
      _resendMessage = null;
      _needsVerification = false;
    });

    final auth = context.read<AuthState>();
    final error = await auth.login(
        email: _emailController.text.trim(),
        password: _passwordController.text);

    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = error;
      // Matches the backend's exact 403 message from auth/routes.py's login().
      _needsVerification =
          error != null && error.toLowerCase().contains('verify your email');
    });
  }

  Future<void> _resend() async {
    setState(() {
      _resendLoading = true;
      _resendMessage = null;
    });
    await context
        .read<AuthState>()
        .resendVerification(_emailController.text.trim());
    if (!mounted) return;
    setState(() {
      _resendLoading = false;
      _resendMessage =
          "If that account exists and isn't verified, we've sent a new link.";
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('Welcome back',
                        style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 4),
                    Text(
                      'Log in to continue chatting with your documents.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 24),
                    TextFormField(
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(labelText: 'Email'),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? 'Email is required' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _passwordController,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Password'),
                      validator: (v) => (v == null || v.isEmpty)
                          ? 'Password is required'
                          : null,
                    ),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => const ForgotPasswordScreen())),
                        child: const Text('Forgot password?'),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 4),
                      Text(_error!,
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.error)),
                      if (_needsVerification)
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton(
                            onPressed: _resendLoading ? null : _resend,
                            child: Text(_resendLoading
                                ? 'Sending...'
                                : 'Resend verification email'),
                          ),
                        ),
                      if (_resendMessage != null)
                        Text(_resendMessage!,
                            style: Theme.of(context).textTheme.bodySmall),
                    ],
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: _loading ? null : _submit,
                      child: Text(_loading ? 'Logging in...' : 'Log in'),
                    ),
                    const SizedBox(height: 16),
                    Center(
                      child: TextButton(
                        onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => const SignupScreen())),
                        child: const Text("Don't have an account? Sign up"),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
