import 'dart:async';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:provider/provider.dart';

import '../../core/api_exception.dart';
import '../../core/auth_state.dart';
import '../../core/voice_settings_state.dart';
import '../../services/voice_service.dart';

enum _PlaybackState { idle, loading, cloning, playing, error }

/// Mirrors frontend/components/ListenButton.tsx: plays the server's TTS for a
/// message, falls back to the device's own text-to-speech if the server voice
/// is unavailable, and — when the user has a voice sample and "My Voice" is
/// on — requests a cloned reading instead (polling until it's ready, same as
/// the web app's clone-request/clone-status flow).
class ListenButton extends StatefulWidget {
  final String text;
  final String messageId;

  const ListenButton({super.key, required this.text, required this.messageId});

  @override
  State<ListenButton> createState() => _ListenButtonState();
}

class _ListenButtonState extends State<ListenButton> {
  final _player = AudioPlayer();
  final _tts = FlutterTts();
  _PlaybackState _state = _PlaybackState.idle;
  String? _errorMessage;
  Timer? _pollTimer;
  // Bumped on every cancel so a network response that arrives after the user
  // already tapped "cancel" can tell it's stale and skip acting on it,
  // instead of clobbering the already-reset idle state.
  int _requestGeneration = 0;

  @override
  void dispose() {
    _pollTimer?.cancel();
    _player.dispose();
    super.dispose();
  }

  Future<void> _playBytes(List<int> bytes) async {
    if (!mounted) return;
    setState(() => _state = _PlaybackState.playing);
    await _player.play(BytesSource(Uint8List.fromList(bytes)));
    _player.onPlayerComplete.first.then((_) {
      if (mounted) setState(() => _state = _PlaybackState.idle);
    });
  }

  Future<void> _speakWithDeviceVoice() async {
    if (!mounted) return;
    _tts.setCompletionHandler(() {
      if (mounted) setState(() => _state = _PlaybackState.idle);
    });
    setState(() => _state = _PlaybackState.playing);
    await _tts.speak(widget.text);
  }

  Future<void> _handleTap() async {
    // Playing -> Stop. Loading/cloning -> cancel (otherwise a second tap while
    // a clone is still generating would start a second overlapping poll cycle
    // instead of canceling the first one).
    if (_state == _PlaybackState.playing ||
        _state == _PlaybackState.loading ||
        _state == _PlaybackState.cloning) {
      _requestGeneration++;
      await _player.stop();
      await _tts.stop();
      _pollTimer?.cancel();
      setState(() => _state = _PlaybackState.idle);
      return;
    }

    final auth = context.read<AuthState>();
    final voiceSettings = context.read<VoiceSettingsState>();
    final service = VoiceService(auth.api);
    final generation = ++_requestGeneration;

    setState(() {
      _state = _PlaybackState.loading;
      _errorMessage = null;
    });

    if (voiceSettings.useMyVoice && voiceSettings.hasVoiceSample) {
      await _playCloned(service, generation);
      return;
    }

    try {
      final bytes =
          await service.speak(text: widget.text, messageId: widget.messageId);
      if (generation != _requestGeneration)
        return; // cancelled while the request was in flight
      await _playBytes(bytes);
    } on ApiException catch (e) {
      if (generation != _requestGeneration) return;
      if (e.status == 503) {
        await _speakWithDeviceVoice();
      } else {
        setState(() {
          _state = _PlaybackState.error;
          _errorMessage = e.detail;
        });
      }
    } catch (_) {
      if (generation != _requestGeneration) return;
      await _speakWithDeviceVoice();
    }
  }

  Future<void> _playCloned(VoiceService service, int generation) async {
    setState(() => _state = _PlaybackState.cloning);
    try {
      final result = await service.cloneRequest(widget.messageId);
      if (generation != _requestGeneration) return;
      if (result['status'] == 'done') {
        final bytes = await service.cloneAudio(result['audio_url'] as String);
        if (generation != _requestGeneration) return;
        await _playBytes(bytes);
        return;
      }

      final jobId = result['job_id'] as String;
      final completer = Completer<void>();
      _pollTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
        if (generation != _requestGeneration) {
          timer.cancel();
          if (!completer.isCompleted) completer.complete();
          return;
        }
        try {
          final status = await service.cloneStatus(jobId);
          if (generation != _requestGeneration) {
            timer.cancel();
            if (!completer.isCompleted) completer.complete();
            return;
          }
          if (status['status'] == 'done') {
            timer.cancel();
            final bytes =
                await service.cloneAudio(status['audio_url'] as String);
            if (generation == _requestGeneration) await _playBytes(bytes);
            if (!completer.isCompleted) completer.complete();
          } else if (status['status'] == 'failed') {
            timer.cancel();
            setState(() {
              _state = _PlaybackState.error;
              _errorMessage =
                  status['error_message'] as String? ?? 'Voice cloning failed.';
            });
            if (!completer.isCompleted) completer.complete();
          }
        } catch (_) {
          timer.cancel();
          if (generation == _requestGeneration) {
            setState(() {
              _state = _PlaybackState.error;
              _errorMessage = "Couldn't check on your voice clone.";
            });
          }
          if (!completer.isCompleted) completer.complete();
        }
      });
      await completer.future.timeout(const Duration(minutes: 5), onTimeout: () {
        _pollTimer?.cancel();
        if (generation == _requestGeneration) {
          setState(() {
            _state = _PlaybackState.error;
            _errorMessage =
                'Voice cloning is taking too long. Please try again.';
          });
        }
      });
    } on ApiException catch (e) {
      if (generation != _requestGeneration) return;
      setState(() {
        _state = _PlaybackState.error;
        _errorMessage = e.detail;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isLoading =
        _state == _PlaybackState.loading || _state == _PlaybackState.cloning;
    final isPlaying = _state == _PlaybackState.playing;

    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 4,
      children: [
        TextButton.icon(
          onPressed: _handleTap,
          icon: isLoading
              ? const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : Icon(isPlaying ? Icons.stop : Icons.volume_up, size: 16),
          label: Text(
            isPlaying
                ? 'Stop'
                : (_state == _PlaybackState.cloning
                    ? 'Generating...'
                    : 'Listen'),
            style: const TextStyle(fontSize: 12),
          ),
          style: TextButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            minimumSize: Size.zero,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ),
        if (_state == _PlaybackState.error && _errorMessage != null)
          Text(_errorMessage!,
              style: TextStyle(
                  fontSize: 11, color: Theme.of(context).colorScheme.error)),
      ],
    );
  }
}
