import 'package:flutter/widgets.dart';

import 'rplanv2_2.dart';
import 'auth_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await PlannerAuth.initialize();
  runApp(const ReplanApp());
}
