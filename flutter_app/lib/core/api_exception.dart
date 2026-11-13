/// Mirrors frontend/lib/api.ts's ApiError — carries the HTTP status and the
/// backend's `detail` message so UI code can show the same text the web app shows.
class ApiException implements Exception {
  final int status;
  final String detail;

  ApiException(this.status, this.detail);

  @override
  String toString() => detail;
}
