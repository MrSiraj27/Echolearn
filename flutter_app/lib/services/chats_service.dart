import 'dart:convert';
import 'package:http/http.dart' as http;

import '../core/api_client.dart';
import '../models/chat.dart';
import '../models/message.dart';

/// One chunk of a streamed assistant reply.
class ChatStreamToken {
  final String content;
  ChatStreamToken(this.content);
}

/// Final event of a stream: citations/follow-ups/the saved message's real id.
class ChatStreamDone {
  final List<Map<String, dynamic>> citations;
  final List<String> followUps;
  final String messageId;
  ChatStreamDone(
      {required this.citations,
      required this.followUps,
      required this.messageId});
}

typedef ChatStreamEvent = Object; // ChatStreamToken | ChatStreamDone

class ChatsService {
  final ApiClient api;

  ChatsService(this.api);

  /// Returns the chat's linked document_ids (needed e.g. to save a flashcard
  /// against the right document) — see ChatDetailResponse in the backend.
  Future<List<String>> documentIds(String chatId) async {
    final data = await api.get('/chats/$chatId', auth: true);
    return (data['document_ids'] as List).cast<String>();
  }

  Future<List<ChatListItem>> list() async {
    final data = await api.get('/chats/', auth: true) as List;
    return data
        .map((e) => ChatListItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<ChatListItem> create(
      {List<String> documentIds = const [], String? title}) async {
    final data = await api.post('/chats/',
        body: {'document_ids': documentIds, 'title': title}, auth: true);
    return ChatListItem(
      id: data['id'] as String,
      title: data['title'] as String?,
      createdAt: DateTime.parse(data['created_at'] as String),
    );
  }

  Future<List<ChatMessage>> messages(String chatId) async {
    final data = await api.get('/chats/$chatId/messages', auth: true) as List;
    return data
        .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<void> delete(String chatId) =>
      api.delete('/chats/$chatId', auth: true);

  Future<void> deleteMessage(String chatId, String messageId) =>
      api.delete('/chats/$chatId/messages/$messageId', auth: true);

  /// Streams the backend's Server-Sent Events for a new message (see
  /// backend/app/chats/routes.py's send_message()): a sequence of
  /// `event: token` chunks followed by one final `event: done`.
  Stream<ChatStreamEvent> sendMessage(String chatId, String content) async* {
    final request =
        http.Request('POST', Uri.parse('${api.baseUrl}/chats/$chatId/message'));
    request.headers['Content-Type'] = 'application/json';
    request.headers['Authorization'] = 'Bearer ${api.accessToken}';
    request.body = jsonEncode({'content': content});

    final streamed = await http.Client().send(request);
    if (streamed.statusCode >= 400) {
      final body = await streamed.stream.bytesToString();
      String detail = 'Something went wrong.';
      try {
        final data = jsonDecode(body);
        if (data is Map && data['detail'] != null)
          detail = data['detail'].toString();
      } catch (_) {}
      throw Exception(detail);
    }

    var buffer = '';
    await for (final chunk in streamed.stream.transform(utf8.decoder)) {
      buffer += chunk;
      // SSE events are separated by a blank line ("\n\n").
      while (buffer.contains('\n\n')) {
        final index = buffer.indexOf('\n\n');
        final rawEvent = buffer.substring(0, index);
        buffer = buffer.substring(index + 2);

        String? eventType;
        String? data;
        for (final line in rawEvent.split('\n')) {
          if (line.startsWith('event: ')) eventType = line.substring(7).trim();
          if (line.startsWith('data: ')) data = line.substring(6);
        }
        if (eventType == null || data == null) continue;

        final payload = jsonDecode(data);
        if (eventType == 'token') {
          yield ChatStreamToken(payload['content'] as String);
        } else if (eventType == 'done') {
          yield ChatStreamDone(
            citations: (payload['citations'] as List? ?? [])
                .cast<Map<String, dynamic>>(),
            followUps: (payload['follow_ups'] as List? ?? []).cast<String>(),
            messageId: payload['message_id'] as String,
          );
        }
      }
    }
  }
}
