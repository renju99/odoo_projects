# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo.addons.base.tests.common import HttpCaseWithUserPortal, HttpCaseWithUserDemo
from odoo.addons.mail.tests.common import mail_new_test_user


@odoo.tests.tagged('-at_install', 'post_install', 'is_tour')
class TestMailPublicPage(HttpCaseWithUserDemo, HttpCaseWithUserPortal):
    """Checks that the invite page redirects to the channel and that all
    modules load correctly on the welcome and channel page when authenticated as various users"""

    def setUp(self):
        super().setUp()
        portal_user = mail_new_test_user(
            self.env,
            name='Portal Bowser',
            login='portal_bowser',
            email='portal_bowser@example.com',
            groups='base.group_portal',
        )
        internal_user = mail_new_test_user(
            self.env,
            name='Internal Luigi',
            login='internal_luigi',
            email='internal_luigi@example.com',
            groups='base.group_user',
        )
        guest = self.env['mail.guest'].create({'name': 'Guest Mario'})

        self.channel = self.env['mail.channel'].browse(self.env['mail.channel'].channel_create(group_id=None, name='Test channel')['id'])
        self.channel.add_members(portal_user.partner_id.ids)
        self.channel.add_members(internal_user.partner_id.ids)
        self.channel.add_members(guest_ids=[guest.id])

        self.group = self.env['mail.channel'].browse(self.env['mail.channel'].create_group(partners_to=(internal_user + portal_user).partner_id.ids, name="Test group")['id'])
        self.group.add_members(guest_ids=[guest.id])

        self.tour = "mail/static/tests/tours/discuss_public_tour.js"

    def _open_channel_page_as_user(self, login):
        self.start_tour(self.channel.invitation_url, self.tour, login=login)
        # Second run of the tour as the first call has side effects, like creating user settings or adding members to
        # the channel, so we need to run it again to test different parts of the code.
        self.start_tour(self.channel.invitation_url, self.tour, login=login)

    def _open_group_page_as_user(self, login):
        self.start_tour(self.group.invitation_url, self.tour, login=login)
        # Second run of the tour as the first call has side effects, like creating user settings or adding members to
        # the channel, so we need to run it again to test different parts of the code.
        self.start_tour(self.group.invitation_url, self.tour, login=login)

    def test_mail_channel_public_page_as_admin(self):
        self._open_channel_page_as_user('admin')

    def test_mail_group_public_page_as_admin(self):
        self._open_group_page_as_user('admin')

    def test_mail_channel_public_page_as_guest(self):
        self.start_tour(self.channel.invitation_url, "mail/static/tests/tours/mail_channel_as_guest_tour.js")
        guest = self.env['mail.guest'].search([('channel_ids', 'in', self.channel.id)], limit=1, order='id desc')
        self.start_tour(self.channel.invitation_url, self.tour, cookies={guest._cookie_name: f"{guest.id}{guest._cookie_separator}{guest.access_token}"})

    def test_mail_group_public_page_as_guest(self):
        self.start_tour(self.group.invitation_url, "mail/static/tests/tours/mail_channel_as_guest_tour.js")
        guest = self.env['mail.guest'].search([('channel_ids', 'in', self.channel.id)], limit=1, order='id desc')
        self.start_tour(self.group.invitation_url, self.tour, cookies={guest._cookie_name: f"{guest.id}{guest._cookie_separator}{guest.access_token}"})

    def test_mail_channel_public_page_as_internal(self):
        self._open_channel_page_as_user('demo')

    def test_mail_group_public_page_as_internal(self):
        self._open_group_page_as_user('demo')

    def test_mail_channel_public_page_as_portal(self):
        self._open_channel_page_as_user('portal')

    def test_mail_group_public_page_as_portal(self):
        self._open_group_page_as_user('portal')

    def test_chat_from_token_as_guest(self):
        self.env['ir.config_parameter'].set_param('mail.chat_from_token', True)
        self.url_open('/chat/xyz')
        channel = self.env['mail.channel'].search([('uuid', '=', 'xyz')])
        self.assertEqual(len(channel), 1)
