import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/plans_service.dart';

/// Mirrors frontend/app/(chat)/upgrade/page.tsx — no real payment flow exists
/// on the web app either (billing isn't enabled), so this just shows plan
/// tiers with a "Contact us" note, same as the web version.
class UpgradeScreen extends StatefulWidget {
  const UpgradeScreen({super.key});

  @override
  State<UpgradeScreen> createState() => _UpgradeScreenState();
}

class _UpgradeScreenState extends State<UpgradeScreen> {
  List<dynamic> _plans = [];
  bool _loading = true;
  bool _contacted = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final plans =
          await PlansService(context.read<AuthState>().api).listPublicPlans();
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
      appBar: AppBar(title: const Text('Upgrade your plan')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text(
                    'Choose the plan that fits how much you use EchoLearn.'),
                const SizedBox(height: 16),
                for (final plan in _plans)
                  _PlanCard(
                      plan: plan,
                      onContact: () => setState(() => _contacted = true)),
                if (_contacted)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text(
                        "Thanks for your interest — billing isn't enabled yet. Reach out to support and "
                        "we'll help you upgrade manually."),
                  ),
              ],
            ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  final Map<String, dynamic> plan;
  final VoidCallback onContact;

  const _PlanCard({required this.plan, required this.onContact});

  @override
  Widget build(BuildContext context) {
    final limits = plan['limits'] as Map<String, dynamic>;
    final price = plan['price_monthly'];
    final priceLabel =
        price == null ? 'Custom' : (price == 0 ? 'Free' : '\$$price/mo');

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(plan['name'] as String,
                style: Theme.of(context).textTheme.titleMedium),
            Text(priceLabel, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            _bullet('${limits['max_documents'] ?? 'Unlimited'} documents'),
            _bullet(
                '${limits['max_file_size_mb'] ?? 'Unlimited'} MB max file size'),
            _bullet(
                '${limits['messages_per_window'] ?? 'Unlimited'} messages / ${limits['message_window_hours']}h'),
            _bullet(
                '${limits['tts_uses_per_day'] ?? 'Unlimited'} voice reads / day'),
            if (limits['priority_processing'] == true)
              _bullet('Priority processing'),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: plan['slug'] == 'free' ? null : onContact,
              child:
                  Text(plan['slug'] == 'free' ? 'Current plan' : 'Contact us'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _bullet(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Row(children: [
          const Icon(Icons.check, size: 14),
          const SizedBox(width: 6),
          Expanded(child: Text(text))
        ]),
      );
}
