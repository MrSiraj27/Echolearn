import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/documents_service.dart';
import '../../services/study_service.dart';
import 'practice_paper_detail_screen.dart';

/// Mirrors the web app's Practice Papers list + generate flow.
class PracticePapersScreen extends StatefulWidget {
  const PracticePapersScreen({super.key});

  @override
  State<PracticePapersScreen> createState() => _PracticePapersScreenState();
}

class _PracticePapersScreenState extends State<PracticePapersScreen> {
  List<dynamic> _papers = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final papers = await StudyService(context.read<AuthState>().api)
          .listPracticePapers();
      if (mounted)
        setState(() {
          _papers = papers;
          _loading = false;
        });
      _pollGeneratingPapers();
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// Same pattern as DocumentsScreen: poll while any paper is still
  /// generating, so the list updates on its own once it's ready/failed.
  void _pollGeneratingPapers() {
    final generating = _papers.any((p) => (p as Map)['status'] == 'generating');
    if (!generating) return;
    Future.delayed(const Duration(seconds: 3), () async {
      if (!mounted) return;
      try {
        final papers = await StudyService(context.read<AuthState>().api)
            .listPracticePapers();
        if (mounted) setState(() => _papers = papers);
      } catch (_) {
        // Transient network hiccup — keep polling rather than giving up for good.
      }
      _pollGeneratingPapers();
    });
  }

  Future<void> _openGenerateDialog() async {
    final docs = await DocumentsService(context.read<AuthState>().api).list();
    final readyDocs = docs.where((d) => d.isReady).toList();
    if (!mounted) return;

    final titleController = TextEditingController(text: 'Practice paper');
    final selected = <String>{};

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Generate practice paper'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                    controller: titleController,
                    decoration: const InputDecoration(labelText: 'Title')),
                const SizedBox(height: 12),
                const Text('Documents'),
                for (final doc in readyDocs)
                  CheckboxListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text(doc.filename),
                    value: selected.contains(doc.id),
                    onChanged: (checked) => setDialogState(() {
                      if (checked == true) {
                        selected.add(doc.id);
                      } else {
                        selected.remove(doc.id);
                      }
                    }),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel')),
            FilledButton(
              onPressed: selected.isEmpty
                  ? null
                  : () => Navigator.of(context).pop(true),
              child: const Text('Generate'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    try {
      await StudyService(context.read<AuthState>().api).generatePracticePaper(
          title: titleController.text.trim(), documentIds: selected.toList());
      _load();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text("Couldn't start generation.")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Practice Papers')),
      floatingActionButton: FloatingActionButton(
          onPressed: _openGenerateDialog, child: const Icon(Icons.add)),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _papers.length,
                itemBuilder: (context, i) {
                  final paper = _papers[i] as Map<String, dynamic>;
                  final status = paper['status'] as String;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: ListTile(
                      title: Text(paper['title'] as String),
                      subtitle: Text(status == 'generating'
                          ? 'Generating...'
                          : status == 'failed'
                              ? (paper['error_message'] as String? ?? 'Failed')
                              : '${paper['total_questions'] ?? '?'} questions • ${paper['total_marks'] ?? '?'} marks'),
                      trailing: status == 'ready'
                          ? const Icon(Icons.chevron_right)
                          : null,
                      onTap: status == 'ready'
                          ? () => Navigator.of(context).push(MaterialPageRoute(
                              builder: (_) => PracticePaperDetailScreen(
                                  paperId: paper['id'] as String)))
                          : null,
                    ),
                  );
                },
              ),
      ),
    );
  }
}
