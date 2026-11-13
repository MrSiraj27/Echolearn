enum MessageRole { user, assistant }

MessageRole messageRoleFromString(String value) =>
    value == 'user' ? MessageRole.user : MessageRole.assistant;

class ChatMessage {
  final String id;
  final MessageRole role;
  String content;
  final List<Map<String, dynamic>>? citations;
  final String contentType;
  final DateTime createdAt;

  ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.citations,
    this.contentType = 'text',
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as String,
      role: messageRoleFromString(json['role'] as String),
      content: json['content'] as String,
      citations: (json['citations'] as List?)?.cast<Map<String, dynamic>>(),
      contentType: json['content_type'] as String? ?? 'text',
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
