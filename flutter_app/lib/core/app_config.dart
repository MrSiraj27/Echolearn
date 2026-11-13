/// Backend base URL. Override at build/run time with:
///   flutter run --dart-define=API_URL=https://echolearn-backend-7j1q.onrender.com
/// Defaults to the production Render URL so a release build works out of the
/// box; point at localhost during local backend development.
const String apiBaseUrl = String.fromEnvironment(
  'API_URL',
  defaultValue: 'https://echolearn-backend-7j1q.onrender.com',
);
