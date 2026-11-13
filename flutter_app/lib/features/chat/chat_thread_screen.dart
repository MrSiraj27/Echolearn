import 'package:flutter/material.dart';

import '../../models/message.dart';
import '../../services/chats_service.dart';
import '../../services/study_service.dart';
import '../../core/auth_state.dart';
import 'package:provider/provider.dart';
import '../voice/listen_button.dart';
import 'chats_service_provider.dart';

/// Mirrors frontend/app/(chat)/chat/[chatId]/page.tsx: message thread, a
/// streaming assistant reply as it arrives, and per-message actions (Listen,
/// Save as flashcard) — same feature set as the web app's chat screen.
class ChatThreadScreen extends StatefulWidget {
  final String chatId;
  final String? title;

  const ChatThreadScreen({super.key, required this.chatId, this.title});

  @override
  State<ChatThreadScreen> createState() => _ChatThreadScreenState();
}

class _ChatThreadScreenState extends State<ChatThreadScreen> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  List<ChatMessage> _messages = [];
  bool _loading = true;
  bool _sending = false;
  String? _error;
  List<String> _documentIds = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final service = chatsServiceOf(context);
    try {
      final messages = await service.messages(widget.chatId);
      final docIds = await service.documentIds(widget.chatId);
      if (!mounted) return;
      setState(() {
        _messages = messages;
        _documentIds = docIds;
        _loading = false;
      });
      _scrollToBottom();
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _send() async {
    final content = _inputController.text.trim();
    if (content.isEmpty || _sending) return;
    _inputController.clear();

    final userMessage = ChatMessage(
      id: 'pending-user-${DateTime.now().microsecondsSinceEpoch}',
      role: MessageRole.user,
      content: content,
      createdAt: DateTime.now(),
    );
    final assistantMessage = ChatMessage(
      id: 'pending-assistant-${DateTime.now().microsecondsSinceEpoch}',
      role: MessageRole.assistant,
      content: '',
      createdAt: DateTime.now(),
    );

    setState(() {
      _messages = [..._messages, userMessage, assistantMessage];
      _sending = true;
      _error = null;
    });
    _scrollToBottom();

    try {
      await for (final event
          in chatsServiceOf(context).sendMessage(widget.chatId, content)) {
        if (event is ChatStreamToken) {
          setState(() => assistantMessage.content += event.content);
          _scrollToBottom();
        } else if (event is ChatStreamDone) {
          // Real ids replace the placeholder ones (used by _saveFlashcard/_delete).
          setState(() {
            final index = _messages.indexOf(assistantMessage);
            if (index != -1) {
              _messages[index] = ChatMessage(
                id: event.messageId,
                role: MessageRole.assistant,
                content: assistantMessage.content,
                citations: event.citations,
                createdAt: DateTime.now(),
              );
            }
          });
        }
      }
    } catch (e) {
      setState(() => _error = 'Something went wrong. Please try again.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _saveFlashcard(ChatMessage assistantMessage) async {
    if (_documentIds.isEmpty) return;
    final userQuestion = _messages
        .sublist(0, _messages.indexOf(assistantMessage))
        .lastWhere((m) => m.role == MessageRole.user,
            orElse: () => assistantMessage)
        .content;

    final auth = context.read<AuthState>();
    final error = await StudyService(auth.api).saveFlashcard(
      documentId: _documentIds.first,
      question: userQuestion,
      answer: assistantMessage.content,
    );

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(error ?? 'Saved as flashcard.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title ?? 'Chat')),
      body: Column(
        children: [
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) {
                      final message = _messages[i];
                      // The placeholder id (set in _send()) is only replaced with the
                      // real message id once the stream's "done" event arrives — showing
                      // Listen/Flashcard before then would hit the backend with an id it
                      // doesn't recognize (still mid-stream, not yet a saved message).
                      final isFinalized = !message.id.startsWith('pending-');
                      return _MessageBubble(
                        message: message,
                        showActions: message.role == MessageRole.assistant &&
                            isFinalized &&
                            message.content.isNotEmpty,
                        onSaveFlashcard:
                            isFinalized ? () => _saveFlashcard(message) : null,
                      );
                    },
                  ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _inputController,
                      decoration: const InputDecoration(
                          hintText: 'Ask about your document...'),
                      minLines: 1,
                      maxLines: 5,
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _sending ? null : _send,
                    icon: _sending
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool showActions;
  final VoidCallback? onSaveFlashcard;

  const _MessageBubble(
      {required this.message, required this.showActions, this.onSaveFlashcard});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;
    final scheme = Theme.of(context).colorScheme;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints:
            BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
        decoration: BoxDecoration(
          color: isUser ? scheme.primary : scheme.secondary,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              message.content.isEmpty ? '...' : message.content,
              style: TextStyle(
                  color: isUser ? scheme.onPrimary : scheme.onSecondary),
            ),
            if (showActions)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Wrap(
                  spacing: 4,
                  children: [
                    ListenButton(text: message.content, messageId: message.id),
                    if (onSaveFlashcard != null)
                      TextButton.icon(
                        onPressed: onSaveFlashcard,
                        icon: const Icon(Icons.bookmark_add_outlined, size: 16),
                        label: const Text('Flashcard',
                            style: TextStyle(fontSize: 12)),
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 6),
                          minimumSize: Size.zero,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
