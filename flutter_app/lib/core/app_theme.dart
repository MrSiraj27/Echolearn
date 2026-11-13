import 'package:flutter/material.dart';

/// Mirrors frontend/app/globals.css's shadcn "neutral" theme (monochrome,
/// ~10px corner radius, near-black primary button in light mode / near-white
/// in dark mode) so the Flutter app looks like the same product as the web app,
/// not a generic Material app.
class AppTheme {
  static const double radius = 10;

  // Light mode (converted from globals.css's oklch light-theme values).
  static const _lightBackground = Color(0xFFFFFFFF);
  static const _lightForeground = Color(0xFF262626);
  static const _lightPrimary = Color(0xFF292929);
  static const _lightPrimaryForeground = Color(0xFFFAFAFA);
  static const _lightMuted = Color(0xFFF5F5F5);
  static const _lightMutedForeground = Color(0xFF8A8A8A);
  static const _lightBorder = Color(0xFFE0E0E0);
  static const _lightDestructive = Color(0xFFD8342A);

  // Dark mode.
  static const _darkBackground = Color(0xFF252525);
  static const _darkForeground = Color(0xFFFAFAFA);
  static const _darkPrimary = Color(0xFFEBEBEB);
  static const _darkPrimaryForeground = Color(0xFF292929);
  static const _darkMuted = Color(0xFF444444);
  static const _darkMutedForeground = Color(0xFFB5B5B5);
  static const _darkBorder = Color(0x1AFFFFFF);
  static const _darkDestructive = Color(0xFFE57373);

  static ThemeData get light => _build(
        brightness: Brightness.light,
        background: _lightBackground,
        foreground: _lightForeground,
        primary: _lightPrimary,
        primaryForeground: _lightPrimaryForeground,
        muted: _lightMuted,
        mutedForeground: _lightMutedForeground,
        border: _lightBorder,
        destructive: _lightDestructive,
      );

  static ThemeData get dark => _build(
        brightness: Brightness.dark,
        background: _darkBackground,
        foreground: _darkForeground,
        primary: _darkPrimary,
        primaryForeground: _darkPrimaryForeground,
        muted: _darkMuted,
        mutedForeground: _darkMutedForeground,
        border: _darkBorder,
        destructive: _darkDestructive,
      );

  static ThemeData _build({
    required Brightness brightness,
    required Color background,
    required Color foreground,
    required Color primary,
    required Color primaryForeground,
    required Color muted,
    required Color mutedForeground,
    required Color border,
    required Color destructive,
  }) {
    final colorScheme = ColorScheme(
      brightness: brightness,
      primary: primary,
      onPrimary: primaryForeground,
      secondary: muted,
      onSecondary: foreground,
      error: destructive,
      onError: primaryForeground,
      surface: background,
      onSurface: foreground,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      textTheme: Typography.material2021()
          .black
          .apply(bodyColor: foreground, displayColor: foreground),
      appBarTheme: AppBarTheme(
          backgroundColor: background,
          foregroundColor: foreground,
          elevation: 0),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: muted,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radius),
          borderSide: BorderSide(color: primary, width: 1.5),
        ),
        labelStyle: TextStyle(color: mutedForeground),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: primaryForeground,
          disabledBackgroundColor: mutedForeground.withValues(alpha: 0.4),
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(radius)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: foreground,
          side: BorderSide(color: border),
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(radius)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: foreground),
      ),
      cardTheme: CardThemeData(
        color: background,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
          side: BorderSide(color: border),
        ),
      ),
      dividerTheme: DividerThemeData(color: border, space: 1),
    );
  }
}
