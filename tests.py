from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from exams.models import Exam, ExamAttempt, Question


class AdminDashboardAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username='su_admin',
            password='Pass12345!',
            email='su@example.com',
            user_type='staff',
        )
        self.student = User.objects.create_user(
            username='stu1',
            password='Pass12345!',
            user_type='student',
        )

    def test_superuser_can_open_console(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_student_forbidden(self):
        self.client.force_login(self.student)
        r = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(r.status_code, 403)

    def test_dashboard_includes_admin_shortcuts_and_sections(self):
        self.client.force_login(self.superuser)
        Exam.objects.create(
            title='Admin console test exam',
            duration_minutes=30,
            created_by=self.superuser,
            status='draft',
        )
        r = self.client.get(reverse('admin_dashboard:dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Recent accounts')
        self.assertContains(r, 'Recent exams')
        self.assertContains(r, 'Review queue')
        self.assertNotContains(r, 'Django admin — data tables')


class AdminToggleActiveTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username='su_toggle',
            password='Pass12345!',
            email='su2@example.com',
            user_type='staff',
        )
        self.target = User.objects.create_user(
            username='toggle_me',
            password='Pass12345!',
            user_type='student',
        )

    def test_toggle_changes_active(self):
        self.client.force_login(self.superuser)
        self.assertTrue(self.target.is_active)
        url = reverse('admin_dashboard:user_toggle_active', args=[self.target.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_toggle_get_not_allowed(self):
        self.client.force_login(self.superuser)
        url = reverse('admin_dashboard:user_toggle_active', args=[self.target.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 405)


class AdminConsoleExtendedPagesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(
            username='su_pages',
            password='Pass12345!',
            email='su3@example.com',
            user_type='staff',
        )
        self.student = User.objects.create_user(
            username='stu_pages',
            password='Pass12345!',
            user_type='student',
        )
        self.exam = Exam.objects.create(
            title='Console list exam',
            duration_minutes=30,
            created_by=self.superuser,
            status='draft',
        )

    def test_student_forbidden_exam_list(self):
        self.client.force_login(self.student)
        r = self.client.get(reverse('admin_dashboard:admin_exams'))
        self.assertEqual(r.status_code, 403)

    def test_superuser_exam_list_and_questions(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse('admin_dashboard:admin_exams'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Console list exam')
        r2 = self.client.get(
            reverse('admin_dashboard:admin_exam_questions', args=[self.exam.pk])
        )
        self.assertEqual(r2.status_code, 200)

    def test_completed_exam_questions_page_is_read_only(self):
        self.client.force_login(self.superuser)
        self.exam.status = 'completed'
        self.exam.save(update_fields=['status'])
        r = self.client.get(
            reverse('admin_dashboard:admin_exam_questions', args=[self.exam.pk])
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Add question')
        self.assertNotContains(r, 'Bulk upload')

    def test_exam_list_filters_by_search_and_status(self):
        self.client.force_login(self.superuser)
        Exam.objects.create(
            title='Physics Final',
            duration_minutes=45,
            created_by=self.superuser,
            status='active',
        )
        r = self.client.get(reverse('admin_dashboard:admin_exams'), {'q': 'physics', 'status': 'active'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Physics Final')
        self.assertNotContains(r, 'Console list exam')

    def test_exam_list_paginates(self):
        self.client.force_login(self.superuser)
        for i in range(15):
            Exam.objects.create(
                title=f'Paged exam {i}',
                duration_minutes=30,
                created_by=self.superuser,
                status='draft',
            )
        r = self.client.get(reverse('admin_dashboard:admin_exams'), {'page': 2})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Page 2 of')

    def test_superuser_performance_page(self):
        self.client.force_login(self.superuser)
        ExamAttempt.objects.create(exam=self.exam, student=self.student, status='submitted', malpractice_score=30)
        r = self.client.get(reverse('admin_dashboard:admin_student_performance'))
        self.assertEqual(r.status_code, 200)

    def test_performance_filter_by_username(self):
        self.client.force_login(self.superuser)
        ExamAttempt.objects.create(exam=self.exam, student=self.student, status='submitted', malpractice_score=20)
        r = self.client.get(reverse('admin_dashboard:admin_student_performance'), {'q': 'stu_pages'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'stu_pages')

    def test_exam_delete_post_removes_exam(self):
        self.client.force_login(self.superuser)
        url = reverse('admin_dashboard:admin_exam_delete', args=[self.exam.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Exam.objects.filter(pk=self.exam.pk).exists())

    def test_exam_delete_get_not_allowed(self):
        self.client.force_login(self.superuser)
        url = reverse('admin_dashboard:admin_exam_delete', args=[self.exam.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 405)

    def test_question_delete_honors_safe_next_redirect(self):
        self.client.force_login(self.superuser)
        q = Question.objects.create(
            exam=self.exam,
            question_text='Q1',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_answer='A',
            marks=1,
            order=1,
        )
        delete_url = reverse('exams:question_delete', args=[self.exam.pk, q.pk])
        next_url = reverse('admin_dashboard:admin_exam_questions', args=[self.exam.pk])
        r = self.client.post(delete_url, data={'next': next_url})
        self.assertRedirects(r, next_url)

    def test_question_delete_ignores_external_next_redirect(self):
        self.client.force_login(self.superuser)
        q = Question.objects.create(
            exam=self.exam,
            question_text='Q2',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_answer='A',
            marks=1,
            order=2,
        )
        delete_url = reverse('exams:question_delete', args=[self.exam.pk, q.pk])
        fallback_url = reverse('exams:question_list', args=[self.exam.pk])
        r = self.client.post(delete_url, data={'next': 'https://evil.example/redirect'})
        self.assertRedirects(r, fallback_url)
