import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from exams.models import Exam, ExamAttempt
from malpractice.models import ExamSession


class MalpracticeViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='staff_user',
            password='Pass12345!',
            user_type='staff',
        )
        self.superuser = User.objects.create_superuser(
            username='admin_user',
            password='Pass12345!',
            email='admin@example.com',
            user_type='staff',
        )
        self.student = User.objects.create_user(
            username='student_user',
            password='Pass12345!',
            user_type='student',
        )
        self.exam = Exam.objects.create(
            title='Unit Test Exam',
            duration_minutes=30,
            created_by=self.staff,
            status='active',
        )
        self.attempt = ExamAttempt.objects.create(
            exam=self.exam,
            student=self.student,
            status='in_progress',
        )
        self.session = ExamSession.objects.create(exam_attempt=self.attempt)

    def test_live_monitoring_api_forbidden_for_student(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('malpractice:live_monitoring_api', args=[self.exam.id]))
        self.assertEqual(response.status_code, 403)

    def test_live_monitoring_api_allows_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('malpractice:live_monitoring_api', args=[self.exam.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('attempts', payload)
        self.assertEqual(len(payload['attempts']), 1)

    def test_heartbeat_returns_live_counts_payload(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('malpractice:heartbeat'),
            data=json.dumps({
                'attempt_id': self.attempt.id,
                'face_count': 0,
                'looking_away': True,
            }),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertIn('counts', payload)
        self.assertEqual(payload['counts']['no_face'], 1)
        self.assertEqual(payload['counts']['looking_away'], 1)
        self.assertEqual(payload['counts']['multiple_faces'], 0)
