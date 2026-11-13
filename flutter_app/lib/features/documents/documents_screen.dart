import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../models/document.dart';
import '../../services/documents_service.dart';
import '../chat/chat_thread_screen.dart';
import '../chat/chats_service_provider.dart';

/// Mirrors frontend's document upload + list (Settings/Documents area): pick a
/// file, upload it, poll its status until ready, then start a chat on it.
class DocumentsScreen extends StatefulWidget {
  const DocumentsScreen({super.key});

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen> {
  late final DocumentsService _service;
  List<DocumentItem> _documents = [];
  bool _loading = true;
  bool _uploading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _service = DocumentsService(context.read<AuthState>().api);
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    try {
      final docs = await _service.list();
      if (!mounted) return;
      setState(() {
        _documents = docs;
        _loading = false;
      });
      _pollProcessingDocuments();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load documents.';
        _loading = false;
      });
    }
  }

  /// Polls any still-processing document every 3s until it's ready/failed —
  /// same pattern as the web app's upload status polling.
  void _pollProcessingDocuments() {
    final processing = _documents.where((d) => d.isProcessing).toList();
    if (processing.isEmpty) return;
    Future.delayed(const Duration(seconds: 3), () async {
      if (!mounted) return;
      await _refresh();
    });
  }

  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(withData: true);
    if (result == null || result.files.isEmpty) return;
    final file = result.files.single;
    if (file.bytes == null) return;

    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      await _service.upload(bytes: file.bytes!, filename: file.name);
      await _refresh();
    } catch (e) {
      setState(() => _error = 'Upload failed. Please try again.');
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _delete(DocumentItem doc) async {
    try {
      await _service.delete(doc.id);
      _refresh();
    } catch (_) {
      if (mounted)
        setState(() => _error = 'Could not delete "${doc.filename}".');
    }
  }

  Future<void> _startChat(DocumentItem doc) async {
    if (!doc.isReady) return;
    final chatsService = chatsServiceOf(context);
    try {
      final chat = await chatsService.create(documentIds: [doc.id]);
      if (!mounted) return;
      Navigator.of(context).push(MaterialPageRoute(
          builder: (_) =>
              ChatThreadScreen(chatId: chat.id, title: chat.title)));
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text("Couldn't start a chat. Please try again.")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Documents')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _uploading ? null : _pickAndUpload,
        icon: _uploading
            ? const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.upload_file),
        label: Text(_uploading ? 'Uploading...' : 'Upload document'),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(_error!,
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.error)),
                    ),
                  if (_documents.isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 48),
                      child: Center(
                          child: Text(
                              'No documents yet. Upload one to start chatting.')),
                    ),
                  for (final doc in _documents)
                    _DocumentTile(
                        doc: doc,
                        onTap: () => _startChat(doc),
                        onDelete: () => _delete(doc)),
                  const SizedBox(height: 80),
                ],
              ),
      ),
    );
  }
}

class _DocumentTile extends StatelessWidget {
  final DocumentItem doc;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _DocumentTile(
      {required this.doc, required this.onTap, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        onTap: doc.isReady ? onTap : null,
        leading: Icon(_statusIcon(doc.status)),
        title: Text(doc.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(_statusLabel(doc.status)),
        trailing: IconButton(
            icon: const Icon(Icons.delete_outline), onPressed: onDelete),
      ),
    );
  }

  IconData _statusIcon(DocumentStatus status) {
    switch (status) {
      case DocumentStatus.ready:
      case DocumentStatus.embedded:
        return Icons.check_circle;
      case DocumentStatus.failed:
        return Icons.error_outline;
      case DocumentStatus.uploaded:
      case DocumentStatus.parsing:
        return Icons.hourglass_top;
    }
  }

  String _statusLabel(DocumentStatus status) {
    switch (status) {
      case DocumentStatus.ready:
      case DocumentStatus.embedded:
        return 'Ready';
      case DocumentStatus.failed:
        return 'Failed to process';
      case DocumentStatus.uploaded:
        return 'Uploaded — waiting to process';
      case DocumentStatus.parsing:
        return 'Processing...';
    }
  }
}
