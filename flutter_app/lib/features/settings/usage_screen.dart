import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/plans_service.dart';
import 'upgrade_screen.dart';

/// Mirrors the web app's usage/quota display: current plan + rolling usage
/// per quota (messages, TTS, voice clones, etc.) from GET /users/me/usage.
class UsageScreen extends StatefulWidget {
  const UsageScreen({super.key});

  @override
  State<UsageScreen> createState() => _UsageScreenState();
}

class _UsageScreenState extends State<UsageScreen> {
  Map<String, dynamic>? _usage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final service = PlansService(context.read<AuthState>().api);
    try {
      final usage = await service.myUsage();
      if (mounted)
        setState(() {
          _usage = usage;
          _loading = false;
        });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Plan & usage'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const UpgradeScreen())),
            child: const Text('Upgrade'),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _usage == null
              ? const Center(child: Text('Could not load usage.'))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text('Plan: ${_usage!['plan_name'] ?? 'Free'}',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 16),
                    for (final quota in (_usage!['quotas'] as List))
                      _QuotaTile(quota: quota as Map<String, dynamic>),
                  ],
                ),
    );
  }
}

class _QuotaTile extends StatelessWidget {
  final Map<String, dynamic> quota;

  const _QuotaTile({required this.quota});

  @override
  Widget build(BuildContext context) {
    final limit = quota['limit'] as int?;
    final used = quota['current_usage'] as int? ?? 0;
    final label = quota['label'] as String? ?? quota['key'] as String;
    final progress =
        limit == null || limit == 0 ? 0.0 : (used / limit).clamp(0.0, 1.0);

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: 4),
          if (limit == null)
            const Text('Unlimited')
          else ...[
            LinearProgressIndicator(
                value: progress, borderRadius: BorderRadius.circular(4)),
            const SizedBox(height: 4),
            Text('$used / $limit'),
          ],
        ],
      ),
    );
  }
}
