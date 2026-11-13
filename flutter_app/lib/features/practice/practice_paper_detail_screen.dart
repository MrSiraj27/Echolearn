import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/study_service.dart';

/// Mirrors the web app's practice paper attempt screen: sections of
/// questions, free-text answers, submit for grading, then results.
class PracticePaperDetailScreen extends StatefulWidget {
  final String paperId;

  const PracticePaperDetailScreen({super.key, required this.paperId});

  @override
  State<PracticePaperDetailScreen> createState() =>
      _PracticePaperDetailScreenState();
}

class _PracticePaperDetailScreenState extends State<PracticePaperDetailScreen> {
  Map<String, dynamic>? _paper;
  final Map<String, TextEditingController> _answerControllers = {};
  Map<String, dynamic>? _result;
  bool _loading = true;
  bool _submitting = false;
  String? _loadError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in _answerControllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final paper = await StudyService(context.read<AuthState>().api)
          .getPracticePaper(widget.paperId);
      if (!mounted) return;
      for (final section in (paper['sections'] as List)) {
        for (final q in (section['questions'] as List)) {
          _answerControllers[q['id'] as String] = TextEditingController();
        }
      }
      setState(() {
        _paper = paper;
        _loading = false;
      });
    } catch (_) {
      if (mounted)
        setState(() {
          _loadError = 'Could not load this practice paper.';
          _loading = false;
        });
    }
  }

  Future<void> _submit() async {
    setState(() => _submitting = true);
    final answers = {
      for (final entry in _answerControllers.entries)
        entry.key: entry.value.text,
    };
    try {
      final result = await StudyService(context.read<AuthState>().api)
          .submitPracticePaper(widget.paperId, answers);
      if (mounted) setState(() => _result = result);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Could not submit. Please try again.')));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar:
          AppBar(title: Text(_paper?['title'] as String? ?? 'Practice paper')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _loadError != null
              ? Center(child: Text(_loadError!))
              : _result != null
                  ? _buildResults()
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        if (_paper!['pattern_note'] != null)
                          Text(_paper!['pattern_note'] as String),
                        const SizedBox(height: 12),
                        for (final section in (_paper!['sections'] as List))
                          _buildSection(section as Map<String, dynamic>),
                        const SizedBox(height: 16),
                        FilledButton(
                          onPressed: _submitting ? null : _submit,
                          child: Text(_submitting
                              ? 'Submitting...'
                              : 'Submit for grading'),
                        ),
                      ],
                    ),
    );
  }

  Widget _buildSection(Map<String, dynamic> section) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(section['title'] as String? ?? 'Section',
            style: Theme.of(context).textTheme.titleMedium),
        for (final q in (section['questions'] as List))
          _buildQuestion(q as Map<String, dynamic>),
        const SizedBox(height: 12),
      ],
    );
  }

  Widget _buildQuestion(Map<String, dynamic> q) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${q['question_text']}  (${q['marks']} marks)'),
            const SizedBox(height: 8),
            if (q['options'] != null && (q['options'] as List).isNotEmpty)
              for (final option in (q['options'] as List))
                RadioListTile<String>(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(option as String),
                  value: option,
                  groupValue: _answerControllers[q['id']]!.text.isEmpty
                      ? null
                      : _answerControllers[q['id']]!.text,
                  onChanged: (v) => setState(
                      () => _answerControllers[q['id']]!.text = v ?? ''),
                )
            else
              TextField(
                controller: _answerControllers[q['id']],
                decoration: const InputDecoration(labelText: 'Your answer'),
                maxLines: 3,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildResults() {
    final results = _result!['results'] as List;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '${_result!['marks_obtained']} / ${_result!['total_marks']}  (${_result!['score_percent']}%)',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 16),
        for (final r in results.cast<Map<String, dynamic>>())
          Card(
            margin: const EdgeInsets.symmetric(vertical: 6),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(r['question_text'] as String? ?? ''),
                  const SizedBox(height: 4),
                  Text('Your answer: ${r['submitted_answer'] ?? '(none)'}'),
                  Text(
                      'Marks: ${r['marks_awarded'] ?? 0} / ${r['marks'] ?? '?'}'),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
