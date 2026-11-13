import '../core/api_client.dart';

class PlansService {
  final ApiClient api;

  PlansService(this.api);

  Future<List<dynamic>> listPublicPlans() async =>
      await api.get('/users/plans', auth: true) as List<dynamic>;

  Future<Map<String, dynamic>> myUsage() async =>
      await api.get('/users/me/usage', auth: true) as Map<String, dynamic>;
}
