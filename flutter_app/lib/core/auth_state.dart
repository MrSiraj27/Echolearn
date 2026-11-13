import 'dart:convert';
import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'api_exception.dart';
import 'token_store.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

/// App-wide session controller. Mirrors frontend/lib/auth-context.tsx: holds
/// whether we're logged in, exposes login/signup/logout, and tries a silent
/// refresh on startup so a returning user doesn't have to log in again every
/// time they open the app.
class AuthState extends ChangeNotifier {
  final ApiClient api;
  final TokenStore tokenStore;

  AuthStatus status = AuthStatus.unknown;

  AuthState({required this.api, required this.tokenStore});

  /// Call once at app startup: tries to silently restore a session from the
  /// persisted refresh token, same as the web app doing a refresh on load.
  Future<void> tryRestoreSession() async {
    final refreshed = await api.tryRefresh();
    status = refreshed ? AuthStatus.authenticated : AuthStatus.unauthenticated;
    notifyListeners();
  }

  /// Returns null on success, or a user-facing error message on failure.
  Future<String?> signup(
      {required String name,
      required String email,
      required String password}) async {
    try {
      final res = await api.rawPost(
          '/auth/signup', {'name': name, 'email': email, 'password': password});
      if (res.statusCode >= 400) {
        return _errorDetail(res.body) ??
            'Something went wrong. Please try again.';
      }
      return null;
    } catch (_) {
      return 'Couldn\'t reach the server. Please check your connection.';
    }
  }

  /// Returns null on success (and updates auth state), or a user-facing error message.
  Future<String?> login(
      {required String email, required String password}) async {
    try {
      final res = await api
          .rawPost('/auth/login', {'email': email, 'password': password});
      if (res.statusCode >= 400) {
        return _errorDetail(res.body) ?? 'Invalid email or password.';
      }

      final refreshToken =
          TokenStore.parseRefreshTokenFromSetCookie(res.headers['set-cookie']);
      if (refreshToken != null) {
        await tokenStore.saveRefreshToken(refreshToken);
      }

      final data = jsonDecode(res.body);
      api.setAccessToken(data['access_token'] as String);
      status = AuthStatus.authenticated;
      notifyListeners();
      return null;
    } catch (_) {
      return 'Couldn\'t reach the server. Please check your connection.';
    }
  }

  Future<void> logout() async {
    api.setAccessToken(null);
    await tokenStore.clearRefreshToken();
    status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  Future<String?> resendVerification(String email) async {
    try {
      await api.post('/auth/resend-verification', body: {'email': email});
      return null;
    } on ApiException catch (e) {
      return e.detail;
    } catch (_) {
      return 'Couldn\'t reach the server. Please check your connection.';
    }
  }

  Future<String?> forgotPassword(String email) async {
    try {
      await api.post('/auth/forgot-password', body: {'email': email});
      return null;
    } on ApiException catch (e) {
      return e.detail;
    } catch (_) {
      return 'Couldn\'t reach the server. Please check your connection.';
    }
  }

  Future<String?> resetPassword(
      {required String token, required String newPassword}) async {
    try {
      await api.post('/auth/reset-password',
          body: {'token': token, 'new_password': newPassword});
      return null;
    } on ApiException catch (e) {
      return e.detail;
    } catch (_) {
      return 'Couldn\'t reach the server. Please check your connection.';
    }
  }

  String? _errorDetail(String body) {
    try {
      final data = jsonDecode(body);
      if (data is Map && data['detail'] != null)
        return data['detail'].toString();
    } catch (_) {}
    return null;
  }
}
