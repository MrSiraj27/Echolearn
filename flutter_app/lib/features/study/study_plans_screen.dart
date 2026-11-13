import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/study_service.dart';
import 'create_study_plan_screen.dart';
import 'study_plan_detail_screen.dart';

/// Mirrors frontend's Study Planner list page.
class StudyPlansScreen extends StatefulWidget {
  const StudyPlansScreen({super.key});

  @override
  State<StudyPlansScreen> createState() => _StudyPlansScreenState();
}

class _StudyPlansScreenState extends State<StudyPlansScreen> {
  List<dynamic> _plans = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final plans =
          await StudyService(context.read<AuthState>().api).listStudyPlans();
      if (mounted)
        setState(() {
          _plans = plans;
          _loading = false;
        });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Study Planner')),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          await Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const CreateStudyPlanScreen()));
          _load();
        },
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _plans.isEmpty
              ? const Center(
                  child: Text(
                      'No study plans yet. Create one from your documents.'))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _plans.length,
                  itemBuilder: (context, i) {
                    final plan = _plans[i] as Map<String, dynamic>;
                    final completed = plan['completed_count'] as int;
                    final total = plan['session_count'] as int;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        title: Text(plan['title'] as String),
                        subtitle: Text(
                            'Exam: ${plan['exam_date']} • $completed/$total sessions done'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () async {
                          await Navigator.of(context).push(MaterialPageRoute(
                              builder: (_) => StudyPlanDetailScreen(
                                  planId: plan['id'] as String)));
                          _load();
                        },
                      ),
                    );
                  },
                ),
    );
  }
}
