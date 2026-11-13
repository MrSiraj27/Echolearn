import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../../core/api_exception.dart';
import '../../core/auth_state.dart';
import '../../core/voice_settings_state.dart';
import '../../services/voice_service.dart';

/// Mirrors the web app's Settings -> Voice Cloning card: record/upload a
/// 3-20s sample, then it's usable via the "My Voice" toggle on any message's
/// Listen button. Recording (not just file-picking) needs a real WAV — the
/// `record` package's AudioEncoder.wav gives the backend exactly what its
/// `wave.open()` parsing expects, matching the constraint in
/// backend/app/voice/clone_routes.py's upload_sample().
class VoiceCloningScreen extends StatefulWidget {
  const VoiceCloningScreen({super.key});

  @override
  State<VoiceCloningScreen> createState() => _VoiceCloningScreenState();
}

class _VoiceCloningScreenState extends State<VoiceCloningScreen> {
  final _recorder = AudioRecorder();
  bool _recording = false;
  bool _uploading = false;
  bool _pregenerate = false;
  String? _error;
  DateTime? _recordStartedAt;

  late final VoiceService _service;

  @override
  void initState() {
    super.initState();
    _service = VoiceService(context.read<AuthState>().api);
    _loadPregenerate();
  }

  Future<void> _loadPregenerate() async {
    try {
      final info = await _service.sampleInfo();
      if (mounted)
        setState(() => _pregenerate = info['pregenerate'] as bool? ?? false);
    } catch (_) {}
  }

  Future<void> _togglePregenerate(bool value) async {
    setState(() => _pregenerate = value);
    try {
      await _service.setPregenerate(value);
    } catch (_) {
      if (mounted) setState(() => _pregenerate = !value); // revert on failure
    }
  }

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!mounted) return;
    if (!hasPermission) {
      setState(() => _error =
          'Microphone permission is required to record a voice sample.');
      return;
    }
    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/voice_sample.wav';
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.wav),
        path: path);
    if (!mounted) return;
    setState(() {
      _recording = true;
      _recordStartedAt = DateTime.now();
      _error = null;
    });
  }

  Future<void> _stopAndUpload() async {
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() => _recording = false);
    if (path == null) return;

    final duration =
        DateTime.now().difference(_recordStartedAt ?? DateTime.now());
    if (duration.inSeconds < 3) {
      setState(() => _error = 'Recording must be at least 3 seconds long.');
      return;
    }

    final consent = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Use this voice?'),
        content: const Text(
            'Only clone your own voice, or a voice you have explicit permission to use. '
            'Do you confirm this recording is your voice or you have that permission?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('I confirm')),
        ],
      ),
    );
    if (!mounted || consent != true) return;

    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      final bytes = await File(path).readAsBytes();
      await _service.uploadSample(bytes, consent: true);
      if (!mounted) return;
      context.read<VoiceSettingsState>().setHasVoiceSample(true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.detail);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  Future<void> _deleteSample() async {
    setState(() => _uploading = true);
    try {
      await _service.deleteSample();
      if (!mounted) return;
      context.read<VoiceSettingsState>().setHasVoiceSample(false);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final voiceSettings = context.watch<VoiceSettingsState>();

    return Scaffold(
      appBar: AppBar(title: const Text('Voice Cloning')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Record a short (3-20 second) reference clip of your voice. Answers can then be '
              'read back using it, instead of the default voice.',
            ),
            const SizedBox(height: 16),
            if (voiceSettings.hasVoiceSample) ...[
              const Text('Voice sample uploaded.',
                  style: TextStyle(color: Colors.green)),
              const SizedBox(height: 12),
              SwitchListTile(
                title: const Text('Use my voice'),
                subtitle:
                    const Text('Applies to every "Listen" button in chat.'),
                value: voiceSettings.useMyVoice,
                onChanged: voiceSettings.setUseMyVoice,
              ),
              SwitchListTile(
                title: const Text('Pre-generate my voice for new answers'),
                subtitle: const Text(
                  'Clones each new reply in the background so Listen is usually instant. '
                  'Uses server CPU and counts toward your daily voice-clone limit even for '
                  'answers you never play.',
                ),
                value: _pregenerate,
                onChanged: _togglePregenerate,
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: _uploading ? null : _deleteSample,
                child: const Text('Delete sample'),
              ),
            ] else ...[
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_error!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                ),
              FilledButton.icon(
                onPressed: _uploading
                    ? null
                    : (_recording ? _stopAndUpload : _startRecording),
                icon: Icon(_recording ? Icons.stop : Icons.mic),
                label: Text(_uploading
                    ? 'Uploading...'
                    : (_recording ? 'Stop & upload' : 'Record voice sample')),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
