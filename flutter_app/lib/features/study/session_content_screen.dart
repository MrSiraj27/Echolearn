import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/study_service.dart';

/// Mirrors the web app's session content view: an explanation plus practice
/// questions generated on demand (backend/app/study/plan_routes.py's
/// get_session_content()).
class SessionContentScreen extends StatefulWidget {
  final String planId;
  final String sessionId;

  const SessionContentScreen(
      {super.key, required this.planId, required this.sessionId});

  @override
  State<SessionContentScreen> createState() => _SessionContentScreenState();
}

class _SessionContentScreenState extends State<SessionContentScreen> {
  Map<String, dynamic>? _content;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final content = await StudyService(context.read<AuthState>().api)
          .sessionContent(widget.planId, widget.sessionId);
      if (mounted)
        setState(() {
          _content = content;
          _loading = false;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          _error = "Couldn't generate content for this session right now.";
          _loading = false;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar:
          AppBar(title: Text(_content?['topic_title'] as String? ?? 'Session')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(_content!['topic_description'] as String,
                        style: Theme.of(context).textTheme.bodyMedium),
                    const Divider(height: 32),
                    Text('Explanation',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text(_content!['explanation'] as String),
                    const Divider(height: 32),
                    Text('Practice questions',
                        style: Theme.of(context).textTheme.titleMedium),
                    for (final q in (_content!['practice_questions'] as List))
                      _QuestionTile(q: q as Map<String, dynamic>),
                  ],
                ),
    );
  }
}

class _QuestionTile extends StatefulWidget {
  final Map<String, dynamic> q;

  const _QuestionTile({required this.q});

  @override
  State<_QuestionTile> createState() => _QuestionTileState();
}

class _QuestionTileState extends State<_QuestionTile> {
  bool _revealed = false;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.q['question'] as String,
                style: const TextStyle(fontWeight: FontWeight.w600)),
            if (widget.q['options'] != null)
              for (final option in (widget.q['options'] as List))
                Text('• $option'),
            const SizedBox(height: 8),
            if (_revealed)
              Text('Answer: ${widget.q['correct_answer']}',
                  style: const TextStyle(color: Colors.green))
            else
              TextButton(
                  onPressed: () => setState(() => _revealed = true),
                  child: const Text('Reveal answer')),
          ],
        ),
      ),
    );
  }
}
