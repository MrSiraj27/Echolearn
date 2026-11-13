import 'dart:convert';
import 'package:http/http.dart' as http;

import '../core/api_client.dart';
import '../core/api_exception.dart';
import '../models/document.dart';

class DocumentsService {
  final ApiClient api;

  DocumentsService(this.api);

  Future<List<DocumentItem>> list() async {
    final data = await api.get('/documents/', auth: true) as List;
    return data
        .map((e) => DocumentItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Returns the new document's id. `bytes` + `filename` come from a file
  /// picker result (works on both mobile and web, unlike a raw File path).
  Future<String> upload(
      {required List<int> bytes, required String filename}) async {
    final request = http.MultipartRequest(
        'POST', Uri.parse('${api.baseUrl}/documents/upload'));
    if (api.accessToken != null) {
      request.headers['Authorization'] = 'Bearer ${api.accessToken}';
    }
    request.files
        .add(http.MultipartFile.fromBytes('file', bytes, filename: filename));

    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);

    if (res.statusCode >= 400) {
      String detail = 'Upload failed.';
      try {
        final data = jsonDecode(res.body);
        if (data is Map && data['detail'] != null)
          detail = data['detail'].toString();
      } catch (_) {}
      throw ApiException(res.statusCode, detail);
    }

    final data = jsonDecode(res.body);
    return data['document_id'] as String;
  }

  Future<DocumentStatus> getStatus(String documentId) async {
    final data = await api.get('/documents/$documentId/status', auth: true);
    return documentStatusFromString(data['status'] as String);
  }

  Future<void> delete(String documentId) =>
      api.delete('/documents/$documentId', auth: true);
}
