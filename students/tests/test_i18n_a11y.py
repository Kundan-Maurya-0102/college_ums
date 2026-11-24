"""Hindi/English switch, in-app help, onboarding tour and keyboard access."""
import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from students.models import StudentProfile

User = get_user_model()
BASE_DIR = Path(settings.BASE_DIR)
PO = BASE_DIR / 'locale' / 'hi' / 'LC_MESSAGES' / 'django.po'
MO = BASE_DIR / 'locale' / 'hi' / 'LC_MESSAGES' / 'django.mo'


class I18nConfigTests(TestCase):
    def test_hindi_and_english_are_available(self):
        codes = [code for code, _ in settings.LANGUAGES]
        self.assertIn('en', codes)
        self.assertIn('hi', codes)

    def test_locale_middleware_is_enabled(self):
        self.assertIn('django.middleware.locale.LocaleMiddleware',
                      settings.MIDDLEWARE)

    def test_locale_path_points_at_project_locale_dir(self):
        self.assertIn(str(BASE_DIR / 'locale'), [str(p) for p in settings.LOCALE_PATHS])
        self.assertTrue(PO.exists(), 'Hindi catalogue missing')

    def test_compiled_catalogue_is_not_stale(self):
        """A .po edit without recompiling silently does nothing — fail loudly."""
        call_command('compile_translations', '--check')

    def test_no_untranslated_strings(self):
        text = PO.read_text(encoding='utf-8')
        empty = [block for block in text.split('\n\n')
                 if 'msgid "' in block and 'msgstr ""\n' in block + '\n'
                 and 'Content-Type' not in block]
        self.assertEqual(empty, [], 'Hindi entries with an empty msgstr')


class LanguageSwitchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('langtest', password='Xyz@12345',
                                             is_staff=True, is_superuser=True)
        self.client = Client(HTTP_HOST='localhost')

    def test_switch_to_hindi_translates_the_navigation(self):
        self.client.force_login(self.user)
        english = self.client.get('/admin-panel/').content.decode()
        self.assertIn('Dashboard', english)

        response = self.client.post(reverse('set_language'),
                                    {'language': 'hi', 'next': '/admin-panel/'})
        self.assertEqual(response.status_code, 302)

        hindi = self.client.get('/admin-panel/').content.decode()
        self.assertIn('डैशबोर्ड', hindi)      # Dashboard
        self.assertIn('लॉग आउट', hindi)       # Logout
        self.assertIn('सूचनाएँ', hindi)        # Notices

    def test_html_lang_attribute_follows_the_language(self):
        self.client.force_login(self.user)
        self.client.post(reverse('set_language'), {'language': 'hi', 'next': '/'})
        body = self.client.get('/admin-panel/').content.decode()
        self.assertIn('<html lang="hi">', body)

    def test_switch_is_available_on_every_page(self):
        self.client.force_login(self.user)
        body = self.client.get('/admin-panel/').content.decode()
        self.assertIn('lang-switch', body)
        self.assertIn('name="language"', body)
        self.assertIn('action="/i18n/setlang/"', body)

    def test_login_page_switch_does_not_break_anonymous_users(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang-switch', response.content.decode())


class HelpCenterTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='localhost')

    def test_staff_sees_admin_help(self):
        admin = User.objects.create_user('helpadmin', password='Xyz@12345',
                                        is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        response = self.client.get(reverse('help_center'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('CSV Upload', body)
        self.assertEqual(body.count('<h1'), 1)

    def test_student_sees_student_help(self):
        student = User.objects.create_user('helpstudent', password='Xyz@12345')
        StudentProfile.objects.create(user=student, name='Help Student',
                                      registration_number='HELP01',
                                      branch='CS', semester=1, year_of_admission=2024)
        self.client.force_login(student)
        body = self.client.get(reverse('help_center')).content.decode()
        self.assertIn('Apply for leave', body)

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse('help_center'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_help_link_is_in_the_layout(self):
        layout = (BASE_DIR / 'templates' / 'base.html').read_text()
        self.assertIn("{% url 'help_center' %}", layout)


class OnboardingTourTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST='localhost')

    def test_tour_payload_is_valid_json_with_title_and_body(self):
        admin = User.objects.create_user('tourist', password='Xyz@12345',
                                        is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        body = self.client.get('/admin-panel/').content.decode()
        match = re.search(r"data-tour-steps='([^']+)'", body)
        self.assertIsNotNone(match, 'tour steps missing from the page')
        steps = json.loads(match.group(1))
        self.assertGreaterEqual(len(steps), 2)
        for step in steps:
            self.assertTrue(step['title'])
            self.assertTrue(step['body'])

    def test_tour_is_not_rendered_for_anonymous_visitors(self):
        body = self.client.get('/login/').content.decode()
        self.assertNotIn('data-tour-steps', body)

    def test_tour_script_and_restart_hook_exist(self):
        script = (BASE_DIR / 'static' / 'js' / 'tour.js').read_text()
        self.assertIn('ums.tour.seen', script)          # shows once
        self.assertIn('data-tour-restart', script)      # replayable from Help
        self.assertIn("event.key === 'Escape'", script)  # keyboard dismissible

    def test_help_page_offers_a_replay_button(self):
        admin = User.objects.create_user('tourhelp', password='Xyz@12345',
                                        is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        body = self.client.get(reverse('help_center')).content.decode()
        self.assertIn('data-tour-restart', body)


class AccessibilityTests(TestCase):
    def test_keyboard_shortcuts_are_implemented_and_documented(self):
        script = (BASE_DIR / 'static' / 'js' / 'ui.js').read_text()
        self.assertIn('global-search', script)
        self.assertIn('main-content', script)
        help_page = (BASE_DIR / 'templates' / 'help_center.html').read_text()
        self.assertIn('<kbd>', help_page)

    def test_reduced_motion_is_respected(self):
        css = (BASE_DIR / 'static' / 'css' / 'theme.css').read_text()
        self.assertIn('prefers-reduced-motion', css)

    def test_skip_link_targets_exist(self):
        layout = (BASE_DIR / 'templates' / 'base.html').read_text()
        self.assertIn('class="skip-link" href="#main-content"', layout)
        self.assertIn('id="main-content"', layout)

    def test_toasts_announce_themselves(self):
        layout = (BASE_DIR / 'templates' / 'base.html').read_text()
        self.assertIn('aria-live="polite"', layout)
