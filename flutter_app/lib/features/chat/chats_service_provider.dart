import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../../core/auth_state.dart';
import '../../services/chats_service.dart';

/// ChatsService is stateless and cheap to construct — rather than threading a
/// Provider<ChatsService> through the whole app, screens just call this with
/// their BuildContext to get one wired to the shared ApiClient/access token.
ChatsService chatsServiceOf(BuildContext context) =>
    ChatsService(context.read<AuthState>().api);
