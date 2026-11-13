import 'dart:convert';
import 'package:http/http.dart' as http;

import '../core/api_client.dart';
import '../core/api_exception.dart';

class VoiceService {
  final ApiClient api;

  VoiceService(this.api);

  /// Server TTS for a message — returns raw WAV bytes, or throws ApiException
  /// (429 = rate/quota limit, 503 = voice backend unavailable), matching
  /// frontend/components/ListenButton.tsx's handling.
  Future<List<int>> speak(
      {required String text,
      required String messageId,
      String? voiceId}) async {
    final res = await http.post(
      Uri.parse('${api.baseUrl}/voice/speak'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${api.accessToken}'
      },
      body: jsonEncode(
          {'text': text, 'message_id': messageId, 'voice_id': voiceId}),
    );
    if (res.statusCode >= 400) {
      String detail = 'Voice synthesis failed.';
      try {
        final data = jsonDecode(res.body);
        if (data is Map && data['detail'] != null)
          detail = data['detail'].toString();
      } catch (_) {}
      throw ApiException(res.statusCode, detail);
    }
    return res.bodyBytes;
  }

  // ---- Voice cloning ----

  Future<Map<String, dynamic>> sampleInfo() async =>
      await api.get('/voice/sample', auth: true) as Map<String, dynamic>;

  /// [consent] must come from an explicit user confirmation that the voice is
  /// their own (or they have the speaker's permission); the backend rejects it otherwise.
  Future<void> uploadSample(List<int> wavBytes, {required bool consent}) async {
    final request = http.MultipartRequest(
        'POST', Uri.parse('${api.baseUrl}/voice/upload-sample'));
    request.headers['Authorization'] = 'Bearer ${api.accessToken}';
    request.fields['consent'] = consent ? 'true' : 'false';
    request.files.add(http.MultipartFile.fromBytes('file', wavBytes,
        filename: 'voice_sample.wav'));
    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);
    if (res.statusCode >= 400) {
      String detail = 'Could not upload voice sample.';
      try {
        final data = jsonDecode(res.body);
        if (data is Map && data['detail'] != null)
          detail = data['detail'].toString();
      } catch (_) {}
      throw ApiException(res.statusCode, detail);
    }
  }

  Future<void> deleteSample() => api.delete('/voice/sample', auth: true);

  Future<void> setPregenerate(bool enabled) =>
      api.patch('/voice/pregenerate', body: {'enabled': enabled}, auth: true);

  /// Returns {"status": "done", "audio_url": ...} or {"status": "queued", "job_id": ...}.
  Future<Map<String, dynamic>> cloneRequest(String messageId) async =>
      await api.post('/voice/clone-request',
          body: {'message_id': messageId}, auth: true) as Map<String, dynamic>;

  Future<Map<String, dynamic>> cloneStatus(String jobId) async =>
      await api.get('/voice/clone-status/$jobId', auth: true)
          as Map<String, dynamic>;

  Future<List<int>> cloneAudio(String path) async {
    final res = await http.get(
      Uri.parse('${api.baseUrl}$path'),
      headers: {'Authorization': 'Bearer ${api.accessToken}'},
    );
    if (res.statusCode >= 400)
      throw ApiException(res.statusCode, 'Could not load cloned audio.');
    return res.bodyBytes;
  }
}
