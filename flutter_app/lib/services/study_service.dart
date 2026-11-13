import '../core/api_client.dart';
import '../core/api_exception.dart';

/// Study Planner + Daily Review + Practice Papers (Phases 15-17), plus the
/// save-as-flashcard call used from the chat thread.
class StudyService {
  final ApiClient api;

  StudyService(this.api);

  // ---- Save-as-flashcard (used from the chat thread) ----

  /// Returns null on success, or a user-facing error (e.g. duplicate card).
  Future<String?> saveFlashcard({
    required String documentId,
    required String question,
    required String answer,
  }) async {
    try {
      await api.post(
        '/review-cards/',
        body: {
          'document_id': documentId,
          'question': question,
          'answer': answer
        },
        auth: true,
      );
      return null;
    } on ApiException catch (e) {
      return e.detail;
    }
  }

  // ---- Daily Review ----

  Future<Map<String, dynamic>> todayReview() async =>
      await api.get('/review/today', auth: true) as Map<String, dynamic>;

  Future<Map<String, dynamic>> submitReview(String cardId, int quality) async =>
      await api.post('/review/$cardId/submit',
          body: {'quality': quality}, auth: true) as Map<String, dynamic>;

  Future<Map<String, dynamic>> reviewStats() async =>
      await api.get('/review/stats', auth: true) as Map<String, dynamic>;

  // ---- Study Planner ----

  Future<List<dynamic>> listStudyPlans() async =>
      await api.get('/study-plans/', auth: true) as List<dynamic>;

  Future<Map<String, dynamic>> previewStudyPlan({
    required String title,
    required String examDate,
    required List<String> documentIds,
    required int dailyStudyMinutes,
  }) async =>
      await api.post(
        '/study-plans/preview',
        body: {
          'title': title,
          'exam_date': examDate,
          'document_ids': documentIds,
          'daily_study_minutes': dailyStudyMinutes,
        },
        auth: true,
      ) as Map<String, dynamic>;

  Future<Map<String, dynamic>> createStudyPlan({
    required String planToken,
    List<String>? reducedTopicTitles,
    required List<String> documentIds,
  }) async =>
      await api.post(
        '/study-plans/',
        body: {
          'plan_token': planToken,
          'reduced_topic_titles': reducedTopicTitles,
          'document_ids': documentIds,
        },
        auth: true,
      ) as Map<String, dynamic>;

  Future<Map<String, dynamic>> getStudyPlan(String planId) async =>
      await api.get('/study-plans/$planId', auth: true) as Map<String, dynamic>;

  Future<void> abandonStudyPlan(String planId) =>
      api.delete('/study-plans/$planId', auth: true);

  Future<Map<String, dynamic>> completeSession(
          String planId, String sessionId) async =>
      await api.post('/study-plans/$planId/sessions/$sessionId/complete',
          auth: true) as Map<String, dynamic>;

  Future<Map<String, dynamic>> skipSession(
          String planId, String sessionId) async =>
      await api.post('/study-plans/$planId/sessions/$sessionId/skip',
          auth: true) as Map<String, dynamic>;

  Future<Map<String, dynamic>> sessionContent(
          String planId, String sessionId) async =>
      await api.get('/study-plans/$planId/sessions/$sessionId/content',
          auth: true) as Map<String, dynamic>;

  // ---- Practice Papers ----

  Future<List<dynamic>> listPracticePapers() async =>
      await api.get('/practice-papers/', auth: true) as List<dynamic>;

  Future<Map<String, dynamic>> generatePracticePaper({
    required String title,
    required List<String> documentIds,
    List<String>? importantTopics,
  }) async =>
      await api.post(
        '/practice-papers/generate',
        body: {
          'title': title,
          'document_ids': documentIds,
          'important_topics': importantTopics
        },
        auth: true,
      ) as Map<String, dynamic>;

  Future<Map<String, dynamic>> getPaperStatus(String paperId) async =>
      await api.get('/practice-papers/$paperId/status', auth: true)
          as Map<String, dynamic>;

  Future<Map<String, dynamic>> getPracticePaper(String paperId) async =>
      await api.get('/practice-papers/$paperId', auth: true)
          as Map<String, dynamic>;

  Future<Map<String, dynamic>> submitPracticePaper(
          String paperId, Map<String, String> answers) async =>
      await api.post('/practice-papers/$paperId/submit',
          body: {'answers': answers}, auth: true) as Map<String, dynamic>;
}
