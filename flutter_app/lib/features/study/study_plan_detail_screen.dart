import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/study_service.dart';
import 'session_content_screen.dart';

/// Mirrors the web app's study plan detail page: session list with
/// complete/skip actions and a "view content" action per session.
class StudyPlanDetailScreen extends StatefulWidget {
  final String planId;

  const StudyPlanDetailScreen({super.key, required this.planId});

  @override
  State<StudyPlanDetailScreen> createState() => _StudyPlanDetailScreenState();
}

class _StudyPlanDetailScreenState extends State<StudyPlanDetailScreen> {
  Map<String, dynamic>? _plan;
  bool _loading = true;
  String? _error;
  late final StudyService _service;

  @override
  void initState() {
    super.initState();
    _service = StudyService(context.read<AuthState>().api);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final plan = await _service.getStudyPlan(widget.planId);
      if (mounted)
        setState(() {
          _plan = plan;
          _loading = false;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          _error = 'Could not load this study plan.';
          _loading = false;
        });
    }
  }

  Future<void> _complete(String sessionId) async {
    try {
      await _service.completeSession(widget.planId, sessionId);
      _load();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not update this session.')));
      }
    }
  }

  Future<void> _skip(String sessionId) async {
    try {
      await _service.skipSession(widget.planId, sessionId);
      _load();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not update this session.')));
      }
    }
  }

  Future<void> _abandon() async {
    try {
      await _service.abandonStudyPlan(widget.planId);
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not abandon this plan.')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_plan?['title'] as String? ?? 'Study plan'),
        actions: [
          IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Abandon plan',
              onPressed: _abandon),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    for (final session in (_plan!['sessions'] as List))
                      _SessionTile(
                        session: session as Map<String, dynamic>,
                        onComplete: () => _complete(session['id'] as String),
                        onSkip: () => _skip(session['id'] as String),
                        onView: () =>
                            Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => SessionContentScreen(
                              planId: widget.planId,
                              sessionId: session['id'] as String),
                        )),
                      ),
                  ],
                ),
    );
  }
}

class _SessionTile extends StatelessWidget {
  final Map<String, dynamic> session;
  final VoidCallback onComplete;
  final VoidCallback onSkip;
  final VoidCallback onView;

  const _SessionTile(
      {required this.session,
      required this.onComplete,
      required this.onSkip,
      required this.onView});

  @override
  Widget build(BuildContext context) {
    final status = session['status'] as String;
    final isPending = status == 'pending';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        title: Text(session['topic_title'] as String),
        subtitle: Text(
            '${session['scheduled_date']} • ${session['session_type']} • $status'),
        onTap: onView,
        trailing: isPending
            ? Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                      icon: const Icon(Icons.check_circle_outline),
                      tooltip: 'Complete',
                      onPressed: onComplete),
                  IconButton(
                      icon: const Icon(Icons.skip_next_outlined),
                      tooltip: 'Skip',
                      onPressed: onSkip),
                ],
              )
            : null,
      ),
    );
  }
}
