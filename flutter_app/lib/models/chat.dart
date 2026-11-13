class ChatListItem {
  final String id;
  final String? title;
  final DateTime createdAt;
  final String? preview;

  ChatListItem(
      {required this.id, this.title, required this.createdAt, this.preview});

  factory ChatListItem.fromJson(Map<String, dynamic> json) {
    return ChatListItem(
      id: json['id'] as String,
      title: json['title'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      preview: json['preview'] as String?,
    );
  }

  String get displayTitle => title ?? 'Untitled chat';
}
