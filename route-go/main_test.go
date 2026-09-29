package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

const (
	testTicketUsername = "riley@un.org"
	testTicketPassword = "ticket-test-password-with-32-chars"
	testAdminUsername  = "operations-admin"
	testAdminPassword  = "admin-test-password-with-32-chars"
)

func configureTestCredentials(t *testing.T) {
	t.Helper()
	t.Setenv("TICKET_USERNAME", testTicketUsername)
	t.Setenv("TICKET_PASSWORD", testTicketPassword)
	t.Setenv("ADMIN_USERNAME", testAdminUsername)
	t.Setenv("ADMIN_PASSWORD", testAdminPassword)
	if err := loadAuthConfig(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		sessions.username = ""
		sessions.password = ""
		sessions.sessions = make(map[string]time.Time)
		adminSessions.username = ""
		adminSessions.password = ""
		adminSessions.sessions = make(map[string]time.Time)
	})
}

func postForm(handler http.HandlerFunc, values url.Values) *httptest.ResponseRecorder {
	request := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(values.Encode()))
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	response := httptest.NewRecorder()
	handler(response, request)
	return response
}

func TestTicketLoginRequiresExactConfiguredUsername(t *testing.T) {
	configureTestCredentials(t)
	wrongUsername := postForm(login, url.Values{
		"username": {"attacker+riley@un.org"},
		"password": {testTicketPassword},
	})
	if wrongUsername.Code != http.StatusUnauthorized {
		t.Fatalf("expected wrong username to be rejected, got %d", wrongUsername.Code)
	}

	validLogin := postForm(login, url.Values{
		"username": {testTicketUsername},
		"password": {testTicketPassword},
	})
	if validLogin.Code != http.StatusSeeOther {
		t.Fatalf("expected configured credentials to be accepted, got %d", validLogin.Code)
	}
	if cookie := validLogin.Result().Cookies(); len(cookie) != 1 || cookie[0].Name != "ticket_session" {
		t.Fatalf("expected ticket session cookie, got %#v", cookie)
	}
}

func TestAdminLoginUsesConfiguredCredentials(t *testing.T) {
	configureTestCredentials(t)
	wrongCredentials := postForm(adminLogin, url.Values{
		"username": {"adm"},
		"password": {"placeholder"},
	})
	if wrongCredentials.Code != http.StatusUnauthorized {
		t.Fatalf("expected source-code credentials to be rejected, got %d", wrongCredentials.Code)
	}

	validLogin := postForm(adminLogin, url.Values{
		"username": {testAdminUsername},
		"password": {testAdminPassword},
	})
	if validLogin.Code != http.StatusSeeOther {
		t.Fatalf("expected configured admin credentials to be accepted, got %d", validLogin.Code)
	}
}

func TestCredentialConfigFailsClosed(t *testing.T) {
	valid := validateCredentialConfig(testTicketUsername, testTicketPassword, testAdminUsername, testAdminPassword)
	if valid != nil {
		t.Fatalf("expected valid credentials, got %v", valid)
	}
	invalidConfigs := []struct {
		name string
		args [4]string
	}{
		{name: "missing username", args: [4]string{"", testTicketPassword, testAdminUsername, testAdminPassword}},
		{name: "short ticket password", args: [4]string{testTicketUsername, "short", testAdminUsername, testAdminPassword}},
		{name: "shared passwords", args: [4]string{testTicketUsername, testTicketPassword, testAdminUsername, testTicketPassword}},
	}
	for _, testCase := range invalidConfigs {
		t.Run(testCase.name, func(t *testing.T) {
			if err := validateCredentialConfig(testCase.args[0], testCase.args[1], testCase.args[2], testCase.args[3]); err == nil {
				t.Fatal("expected invalid credential configuration to fail")
			}
		})
	}
}
