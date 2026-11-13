import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/study_service.dart';

/// Mirrors the web app's Daily Review (spaced repetition) screen: shows one
/// due card at a time, question -> reveal answer -> grade 0-5 (SM-2 quality),
/// matching backend/app/study/review_routes.py.
class DailyReviewScreen extends StatefulWidget {
  const DailyReviewScreen({super.key});

  @override
  State<DailyReviewScreen> createState() => _DailyReviewScreenState();
}

class _DailyReviewScreenState extends State<DailyReviewScreen> {
  List<dynamic> _cards = [];
  int _index = 0;
  bool _revealed = false;
  bool _loading = true;
  int _totalDue = 0;
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
      final data = await _service.todayReview();
      if (!mounted) return;
      setState(() {
        _cards = data['cards'] as List;
        _totalDue = data['total_due'] as int;
        _index = 0;
        _revealed = false;
        _loading = false;
      });
    } catch (_) {
      if (mounted)
        setState(() {
          _error = "Couldn't load today's review cards.";
          _loading = false;
        });
    }
  }

  Future<void> _grade(int quality) async {
    final card = _cards[_index] as Map<String, dynamic>;
    await _service.submitReview(card['id'] as String, quality);
    setState(() {
      _index++;
      _revealed = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Daily Review')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _cards.isEmpty
                  ? const Center(child: Text('No cards due today. Nice work!'))
                  : _index >= _cards.length
                      ? Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Text("You're all caught up for today!"),
                              const SizedBox(height: 12),
                              FilledButton(
                                  onPressed: _load,
                                  child: const Text('Refresh')),
                            ],
                          ),
                        )
                      : _buildCard(_cards[_index] as Map<String, dynamic>),
    );
  }

  Widget _buildCard(Map<String, dynamic> card) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text('${_index + 1} / ${_cards.length}  (of $_totalDue due today)',
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(card['question'] as String,
                      style: Theme.of(context).textTheme.titleMedium),
                  if (_revealed) ...[
                    const Divider(height: 24),
                    Text(card['answer'] as String),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          if (!_revealed)
            FilledButton(
                onPressed: () => setState(() => _revealed = true),
                child: const Text('Reveal answer'))
          else
            Wrap(
              spacing: 8,
              alignment: WrapAlignment.center,
              children: [
                _gradeButton('Again', 0),
                _gradeButton('Hard', 2),
                _gradeButton('Good', 4),
                _gradeButton('Easy', 5),
              ],
            ),
        ],
      ),
    );
  }

  Widget _gradeButton(String label, int quality) =>
      OutlinedButton(onPressed: () => _grade(quality), child: Text(label));
}
