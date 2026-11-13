import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/chat.dart';
import '../documents/documents_screen.dart';
import '../practice/practice_papers_screen.dart';
import '../settings/settings_screen.dart';
import '../study/daily_review_screen.dart';
import '../study/study_plans_screen.dart';
import 'chat_thread_screen.dart';
import 'chats_service_provider.dart';

/// Mirrors frontend's chat sidebar/list — the app's home screen once
/// authenticated (replaces HomePlaceholderScreen from Phase 3).
class ChatsListScreen extends StatefulWidget {
  const ChatsListScreen({super.key});

  @override
  State<ChatsListScreen> createState() => _ChatsListScreenState();
}

class _ChatsListScreenState extends State<ChatsListScreen> {
  List<ChatListItem> _chats = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    try {
      final chats = await chatsServiceOf(context).list();
      if (!mounted) return;
      setState(() {
        _chats = chats;
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _delete(ChatListItem chat) async {
    // Dismissible requires the item to actually leave the list once dismissed
    // (otherwise it throws "a dismissed Dismissible widget is still part of
    // the tree" on the next rebuild) — so remove it from local state right
    // away rather than waiting on a full server round-trip + _refresh().
    final removedIndex = _chats.indexOf(chat);
    setState(() => _chats.removeWhere((c) => c.id == chat.id));
    try {
      await chatsServiceOf(context).delete(chat.id);
    } catch (_) {
      if (mounted) {
        setState(
            () => _chats.insert(removedIndex.clamp(0, _chats.length), chat));
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not delete this chat.')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chats'),
        actions: [
          IconButton(
            icon: const Icon(Icons.folder_open),
            tooltip: 'Documents',
            onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const DocumentsScreen())),
          ),
        ],
      ),
      drawer: const _AppDrawer(),
      floatingActionButton: FloatingActionButton(
        onPressed: () => Navigator.of(context)
            .push(MaterialPageRoute(builder: (_) => const DocumentsScreen())),
        child: const Icon(Icons.add),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _chats.isEmpty
                ? ListView(
                    children: const [
                      Padding(
                        padding: EdgeInsets.only(top: 80),
                        child: Center(
                            child: Text(
                                'No chats yet. Upload a document to start one.')),
                      ),
                    ],
                  )
                : ListView.builder(
                    itemCount: _chats.length,
                    itemBuilder: (context, i) {
                      final chat = _chats[i];
                      return Dismissible(
                        key: ValueKey(chat.id),
                        direction: DismissDirection.endToStart,
                        background: Container(
                          color: Theme.of(context).colorScheme.error,
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: 20),
                          child: const Icon(Icons.delete, color: Colors.white),
                        ),
                        onDismissed: (_) => _delete(chat),
                        child: ListTile(
                          title: Text(chat.displayTitle,
                              maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle: chat.preview != null
                              ? Text(chat.preview!,
                                  maxLines: 1, overflow: TextOverflow.ellipsis)
                              : null,
                          trailing:
                              Text(DateFormat.MMMd().format(chat.createdAt)),
                          onTap: () => Navigator.of(context)
                              .push(MaterialPageRoute(
                                  builder: (_) => ChatThreadScreen(
                                      chatId: chat.id, title: chat.title)))
                              .then((_) => _refresh()),
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}

/// Mirrors the web app's Sidebar sections beyond chats — Documents lives as
/// an AppBar action above since it's used constantly; these are the
/// less-frequent areas (mirrors Prompts 27-31: plans/quotas, Study Planner,
/// Daily Review, Practice Papers).
class _AppDrawer extends StatelessWidget {
  const _AppDrawer();

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: ListView(
          children: [
            const DrawerHeader(
                child: Align(
                    alignment: Alignment.bottomLeft, child: Text('EchoLearn'))),
            ListTile(
              leading: const Icon(Icons.folder_open),
              title: const Text('Documents'),
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const DocumentsScreen()));
              },
            ),
            ListTile(
              leading: const Icon(Icons.calendar_month),
              title: const Text('Study Planner'),
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const StudyPlansScreen()));
              },
            ),
            ListTile(
              leading: const Icon(Icons.style),
              title: const Text('Daily Review'),
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const DailyReviewScreen()));
              },
            ),
            ListTile(
              leading: const Icon(Icons.description_outlined),
              title: const Text('Practice Papers'),
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const PracticePapersScreen()));
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.settings),
              title: const Text('Settings'),
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const SettingsScreen()));
              },
            ),
          ],
        ),
      ),
    );
  }
}
