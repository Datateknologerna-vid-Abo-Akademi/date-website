from django.test import TestCase

from staticpages.models import StaticPageNav, StaticUrl


class StaticUrlModelTests(TestCase):
    def test_save_assigns_first_dropdown_element_for_category(self):
        category = StaticPageNav.objects.create(category_name="About")

        item = StaticUrl.objects.create(
            title="First link",
            url="/first/",
            category=category,
            dropdown_element=None,
        )

        self.assertEqual(item.dropdown_element, 10)

    def test_save_increments_dropdown_element_within_category(self):
        category = StaticPageNav.objects.create(category_name="About")
        other_category = StaticPageNav.objects.create(category_name="Other")
        StaticUrl.objects.create(
            title="Existing link",
            url="/existing/",
            category=category,
            dropdown_element=20,
        )
        StaticUrl.objects.create(
            title="Other category link",
            url="/other/",
            category=other_category,
            dropdown_element=90,
        )

        item = StaticUrl.objects.create(
            title="Next link",
            url="/next/",
            category=category,
            dropdown_element=None,
        )

        self.assertEqual(item.dropdown_element, 30)
