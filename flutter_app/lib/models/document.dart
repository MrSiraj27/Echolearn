enum DocumentStatus { uploaded, parsing, embedded, ready, failed }

DocumentStatus documentStatusFromString(String value) {
  return DocumentStatus.values
      .firstWhere((s) => s.name == value, orElse: () => DocumentStatus.failed);
}

class DocumentItem {
  final String id;
  final String filename;
  final String fileType;
  final DocumentStatus status;
  final DateTime createdAt;
  final String? summary;
  final List<String> suggestedQuestions;
  final String? folderId;

  DocumentItem({
    required this.id,
    required this.filename,
    required this.fileType,
    required this.status,
    required this.createdAt,
    this.summary,
    this.suggestedQuestions = const [],
    this.folderId,
  });

  factory DocumentItem.fromJson(Map<String, dynamic> json) {
    return DocumentItem(
      id: json['id'] as String,
      filename: json['filename'] as String,
      fileType: json['file_type'] as String,
      status: documentStatusFromString(json['status'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      summary: json['summary'] as String?,
      suggestedQuestions:
          (json['suggested_questions'] as List?)?.cast<String>() ?? const [],
      folderId: json['folder_id'] as String?,
    );
  }

  bool get isReady =>
      status == DocumentStatus.embedded || status == DocumentStatus.ready;
  bool get isProcessing =>
      status == DocumentStatus.uploaded || status == DocumentStatus.parsing;
  bool get isFailed => status == DocumentStatus.failed;
}
