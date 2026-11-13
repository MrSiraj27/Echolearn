import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/documents_service.dart';
import '../../services/study_service.dart';

/// Mirrors the web app's create-study-plan flow: pick ready documents, an exam
/// date and a daily-minutes budget, preview the generated topics/sessions,
/// then confirm to actually create it (backend/app/study/plan_routes.py's
/// two-step preview -> create with the returned plan_token).
class CreateStudyPlanScreen extends StatefulWidget {
  const CreateStudyPlanScreen({super.key});

  @override
  State<CreateStudyPlanScreen> createState() => _CreateStudyPlanScreenState();
}

class _CreateStudyPlanScreenState extends State<CreateStudyPlanScreen> {
  final _titleController = TextEditingController(text: 'My study plan');
  DateTime _examDate = DateTime.now().add(const Duration(days: 14));
  int _dailyMinutes = 45;
  final Set<String> _selectedDocumentIds = {};
  List<dynamic> _readyDocuments = [];
  Map<String, dynamic>? _preview;
  bool _loadingDocs = true;
  bool _previewing = false;
  bool _creating = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDocuments();
  }

  @override
  void dispose() {
    _titleController.dispose();
    super.dispose();
  }

  Future<void> _loadDocuments() async {
    try {
      final docs = await DocumentsService(context.read<AuthState>().api).list();
      if (!mounted) return;
      setState(() {
        _readyDocuments = docs.where((d) => d.isReady).toList();
        _loadingDocs = false;
      });
    } catch (_) {
      if (mounted)
        setState(() {
          _error = 'Could not load your documents.';
          _loadingDocs = false;
        });
    }
  }

  Future<void> _generatePreview() async {
    if (_selectedDocumentIds.isEmpty) {
      setState(() => _error = 'Select at least one document.');
      return;
    }
    setState(() {
      _previewing = true;
      _error = null;
    });
    try {
      final result =
          await StudyService(context.read<AuthState>().api).previewStudyPlan(
        title: _titleController.text.trim(),
        examDate: _examDate.toIso8601String().split('T').first,
        documentIds: _selectedDocumentIds.toList(),
        dailyStudyMinutes: _dailyMinutes,
      );
      if (mounted) setState(() => _preview = result);
    } catch (_) {
      if (mounted)
        setState(() =>
            _error = "Couldn't generate a plan from this material right now.");
    } finally {
      if (mounted) setState(() => _previewing = false);
    }
  }

  Future<void> _confirmCreate() async {
    if (_preview == null) return;
    setState(() => _creating = true);
    try {
      await StudyService(context.read<AuthState>().api).createStudyPlan(
        planToken: _preview!['plan_token'] as String,
        documentIds: _selectedDocumentIds.toList(),
      );
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted)
        setState(() => _error = 'Could not create the plan. Please try again.');
    } finally {
      if (mounted) setState(() => _creating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New study plan')),
      body: _loadingDocs
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                TextField(
                    controller: _titleController,
                    decoration: const InputDecoration(labelText: 'Title')),
                const SizedBox(height: 16),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Exam date'),
                  subtitle: Text(_examDate.toIso8601String().split('T').first),
                  trailing: const Icon(Icons.calendar_today),
                  onTap: () async {
                    final picked = await showDatePicker(
                      context: context,
                      initialDate: _examDate,
                      firstDate: DateTime.now().add(const Duration(days: 1)),
                      lastDate:
                          DateTime.now().add(const Duration(days: 365 * 2)),
                    );
                    if (picked != null) setState(() => _examDate = picked);
                  },
                ),
                Row(
                  children: [
                    const Text('Daily minutes: '),
                    Expanded(
                      child: Slider(
                        value: _dailyMinutes.toDouble(),
                        min: 10,
                        max: 180,
                        divisions: 17,
                        label: '$_dailyMinutes',
                        onChanged: (v) =>
                            setState(() => _dailyMinutes = v.round()),
                      ),
                    ),
                    Text('$_dailyMinutes'),
                  ],
                ),
                const SizedBox(height: 8),
                const Text('Documents',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                for (final doc in _readyDocuments)
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(doc.filename),
                    value: _selectedDocumentIds.contains(doc.id),
                    onChanged: (checked) => setState(() {
                      if (checked == true) {
                        _selectedDocumentIds.add(doc.id);
                      } else {
                        _selectedDocumentIds.remove(doc.id);
                      }
                    }),
                  ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(_error!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error)),
                  ),
                const SizedBox(height: 12),
                if (_preview == null)
                  FilledButton(
                    onPressed: _previewing ? null : _generatePreview,
                    child: Text(
                        _previewing ? 'Generating preview...' : 'Preview plan'),
                  )
                else ...[
                  Text(
                      '${(_preview!['sessions'] as List).length} sessions across '
                      '${(_preview!['topics'] as List).length} topics'),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _creating ? null : _confirmCreate,
                    child: Text(_creating ? 'Creating...' : 'Create this plan'),
                  ),
                ],
              ],
            ),
    );
  }
}
