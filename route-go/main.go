package main

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type option struct {
	Name     string   `json:"name"`
	Children []option `json:"children,omitempty"`
}

var ticketCatalog = []option{
	{Name: "Communications Services", Children: []option{
		{Name: "Unite Comms Telephone Service", Children: []option{{Name: "Call Quality Issue", Children: []option{{Name: "Call Quality Issue (NY-based users only)"}, {Name: "Incident PC Software Issue"}}}, {Name: "Caller ID Issue"}, {Name: "Other Issue"}}},
		{Name: "Wireless Cellular Service", Children: []option{{Name: "Wireless Cellular Service Issue"}}},
	}},
	{Name: "Hosting Services", Children: []option{
		{Name: "Bastion Host Service", Children: []option{{Name: "Bastion Issue"}, {Name: "Bastion Host Registration Request"}}},
		{Name: "Database Hosting Service", Children: []option{{Name: "Database Hosting Login Issue"}, {Name: "Database Hosting Other Issue"}}},
		{Name: "Git Version Control System (VCS) Service", Children: []option{{Name: "Incident GIT VCS Issue"}}},
		{Name: "Jira/Confluence Service", Children: []option{{Name: "Incident Jira/Confluence Issue"}}},
		{Name: "Netscaler", Children: []option{{Name: "Incident Netscaler Issue"}, {Name: "Registration Request", Children: []option{{Name: "Port 80/443"}, {Name: "Non-Prepared port (any other than 80 or 443)"}}}}},
		{Name: "Storage Provisioning Service", Children: []option{{Name: "Incident Storage Issue"}}},
		{Name: "TLS Certificate Registration Service", Children: []option{{Name: "Request to Create TLS Certificate"}, {Name: "Request to Renew TLS Certificate"}, {Name: "Request for Internal TLS Certificate"}, {Name: "Request to Validate Domain"}}},
		{Name: "Web Hosting Service", Children: []option{{Name: "Incident Web Hosting Issue"}, {Name: "Incident Unite Web Issue"}}},
	}},
	{Name: "Network Services", Children: []option{
		{Name: "Domain Name System (DNS) Service", Children: []option{{Name: "Incident DNS Issue"}, {Name: "DNS Registration Request"}}},
		{Name: "Firewall Service", Children: []option{{Name: "Incident Firewall Issue"}, {Name: "Firewall Rule Amendment Request"}}},
		{Name: "LAN Outlet Service", Children: []option{{Name: "Incident LAN Issue"}}},
		{Name: "WiFi Internet Access", Children: []option{{Name: "Incident WiFi Wireless Access Point Issue"}}},
	}},
	{Name: "Personal Computing Services", Children: []option{
		{Name: "Managed Output Service", Children: []option{{Name: "Authentication/Card Reader Issue"}, {Name: "Consumables Issue"}, {Name: "Misc Error Code Issue"}, {Name: "PaperJam"}, {Name: "Print Quality Issue"}, {Name: "Unable to Print, Scan, Copy, or Fax"}}},
		{Name: "Network Accounts", Children: []option{{Name: "Incident UNHQ Domain Network Account Login Issue"}}},
		{Name: "PC Hardware", Children: []option{{Name: "Lost/Stolen Laptop"}, {Name: "Hardware Issue"}, {Name: "New/Replacement Equipment Request"}}},
		{Name: "PC Software", Children: []option{{Name: "Incident PC Software Issue"}}},
		{Name: "UNHQ VPN", Children: []option{{Name: "Incident UNHQ VPN Issue"}}},
	}},
	{Name: "Request for Information", Children: []option{{Name: "Request For Information"}}},
	{Name: "SMT Services", Children: []option{
		{Name: "ICT Focal Points", Children: []option{{Name: "ICT Coordinator/TFP Registration Request"}}},
		{Name: "Submitters & Approvers List", Children: []option{{Name: "Unite Self Service Submitter Registration"}, {Name: "Unite Self Service Approver Registration"}, {Name: "Unite Self Service New Organization"}, {Name: "Unite Self Service Training Request"}}},
	}},
}

var guideRequests uint64

type authStore struct {
	password string
	sessions map[string]time.Time
	mu       sync.Mutex
}

var sessions = authStore{
	password: envOrDefault("TICKET_PASSWORD", "ticket-management-dev"),
	sessions: make(map[string]time.Time),
}

var adminSessions = struct {
	sessions map[string]time.Time
	mu       sync.Mutex
}{sessions: make(map[string]time.Time)}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func newSession() (string, error) {
	token := make([]byte, 32)
	if _, err := rand.Read(token); err != nil {
		return "", err
	}
	id := fmt.Sprintf("%x", token)
	sessions.mu.Lock()
	sessions.sessions[id] = time.Now().Add(8 * time.Hour)
	sessions.mu.Unlock()
	return id, nil
}

func authenticated(r *http.Request) bool {
	cookie, err := r.Cookie("ticket_session")
	if err != nil {
		return false
	}
	sessions.mu.Lock()
	expires, found := sessions.sessions[cookie.Value]
	if found && time.Now().After(expires) {
		delete(sessions.sessions, cookie.Value)
		found = false
	}
	sessions.mu.Unlock()
	return found
}

func requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !authenticated(r) {
			http.Redirect(w, r, "/login", http.StatusSeeOther)
			return
		}
		next(w, r)
	}
}

func login(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		_ = loginTemplate.Execute(w, nil)
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid login request", http.StatusBadRequest)
		return
	}
	username := r.FormValue("username")
	password := r.FormValue("password")
	// Temporary access provision: accept any username containing the UN email domain.
	validUser := strings.Contains(strings.ToLower(username), "@un.org")
	validPassword := subtle.ConstantTimeCompare([]byte(password), []byte(sessions.password)) == 1
	if !validUser || !validPassword {
		w.WriteHeader(http.StatusUnauthorized)
		_ = loginTemplate.Execute(w, "The username or password was not recognized.")
		return
	}
	token, err := newSession()
	if err != nil {
		http.Error(w, "unable to create session", http.StatusInternalServerError)
		return
	}
	http.SetCookie(w, &http.Cookie{Name: "ticket_session", Value: token, Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode, MaxAge: 8 * 60 * 60})
	http.Redirect(w, r, "/", http.StatusSeeOther)
}

func logout(w http.ResponseWriter, r *http.Request) {
	if cookie, err := r.Cookie("ticket_session"); err == nil {
		sessions.mu.Lock()
		delete(sessions.sessions, cookie.Value)
		sessions.mu.Unlock()
	}
	http.SetCookie(w, &http.Cookie{Name: "ticket_session", Value: "", Path: "/", MaxAge: -1, HttpOnly: true, SameSite: http.SameSiteLaxMode})
	http.Redirect(w, r, "/login", http.StatusSeeOther)
}

func newAdminSession() (string, error) {
	token := make([]byte, 32)
	if _, err := rand.Read(token); err != nil {
		return "", err
	}
	id := fmt.Sprintf("%x", token)
	adminSessions.mu.Lock()
	adminSessions.sessions[id] = time.Now().Add(8 * time.Hour)
	adminSessions.mu.Unlock()
	return id, nil
}

func adminAuthenticated(r *http.Request) bool {
	cookie, err := r.Cookie("admin_session")
	if err != nil {
		return false
	}
	adminSessions.mu.Lock()
	expires, found := adminSessions.sessions[cookie.Value]
	if found && time.Now().After(expires) {
		delete(adminSessions.sessions, cookie.Value)
		found = false
	}
	adminSessions.mu.Unlock()
	return found
}

func requireAdmin(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !adminAuthenticated(r) {
			http.Redirect(w, r, "/admin/login", http.StatusSeeOther)
			return
		}
		next(w, r)
	}
}

func adminLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		_ = adminLoginTemplate.Execute(w, nil)
		return
	}
	if err := r.ParseForm(); err != nil {
		http.Error(w, "invalid admin login request", http.StatusBadRequest)
		return
	}
	validUser := subtle.ConstantTimeCompare([]byte(r.FormValue("username")), []byte("adm")) == 1
	validPassword := subtle.ConstantTimeCompare([]byte(r.FormValue("password")), []byte("placeholder")) == 1
	if !validUser || !validPassword {
		w.WriteHeader(http.StatusUnauthorized)
		_ = adminLoginTemplate.Execute(w, "The administrator username or password was not recognized.")
		return
	}
	token, err := newAdminSession()
	if err != nil {
		http.Error(w, "unable to create admin session", http.StatusInternalServerError)
		return
	}
	http.SetCookie(w, &http.Cookie{Name: "admin_session", Value: token, Path: "/admin", HttpOnly: true, SameSite: http.SameSiteLaxMode, MaxAge: 8 * 60 * 60})
	http.Redirect(w, r, "/admin", http.StatusSeeOther)
}

func adminLogout(w http.ResponseWriter, r *http.Request) {
	if cookie, err := r.Cookie("admin_session"); err == nil {
		adminSessions.mu.Lock()
		delete(adminSessions.sessions, cookie.Value)
		adminSessions.mu.Unlock()
	}
	http.SetCookie(w, &http.Cookie{Name: "admin_session", Value: "", Path: "/admin", MaxAge: -1, HttpOnly: true, SameSite: http.SameSiteLaxMode})
	http.Redirect(w, r, "/admin/login", http.StatusSeeOther)
}

func adminDashboard(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_ = adminDashboardTemplate.Execute(w, map[string]string{"GuideRequests": formatUint(atomic.LoadUint64(&guideRequests))})
}

func health(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func metrics(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	_, _ = w.Write([]byte("# HELP route_go_up Whether the route service is responding.\n# TYPE route_go_up gauge\nroute_go_up 1\n# HELP route_go_ticket_guide_requests_total Total requests served by the ticket guide.\n# TYPE route_go_ticket_guide_requests_total counter\nroute_go_ticket_guide_requests_total " + formatUint(atomic.LoadUint64(&guideRequests)) + "\n"))
}

func formatUint(value uint64) string {
	if value == 0 {
		return "0"
	}
	var digits [20]byte
	index := len(digits)
	for value > 0 {
		index--
		digits[index] = byte('0' + value%10)
		value /= 10
	}
	return string(digits[index:])
}

var adminLoginTemplate = template.Must(template.New("admin-login").Parse(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin sign in | ICT Service Desk</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#17212b;background:#edf1f5}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:linear-gradient(135deg,#e5edf1,#f8f5f0)}.card{width:min(430px,100%);background:#fff;border:1px solid #d6e1e8;border-radius:18px;box-shadow:0 20px 55px #24374618;overflow:hidden}.brand{padding:30px 34px;background:#17212b;color:#fff}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#f2a27f;font-weight:700}.brand h1{margin:9px 0 0;font-size:29px;line-height:1.1}.form{padding:30px 34px}.form p{margin:0 0 22px;color:#617681}.field{display:grid;gap:7px;margin-bottom:16px}.field label{font-size:13px;font-weight:700;color:#48636d}.field input{width:100%;border:1px solid #cad8de;border-radius:9px;padding:13px;font:inherit}.field input:focus{outline:0;border-color:#e16b45;box-shadow:0 0 0 3px #e16b4522}.submit{width:100%;border:0;border-radius:9px;background:#e16b45;color:#fff;padding:14px;font:inherit;font-weight:700;cursor:pointer}.submit:hover{background:#c95532}.error{color:#a53f2e;background:#fff1ed;border-radius:8px;padding:11px;margin-bottom:17px;font-size:14px}</style></head><body><main class="card"><header class="brand"><div class="eyebrow">Operations console</div><h1>Analytics sign in</h1></header><form class="form" method="post" action="/admin/login"><p>Review ticket guide activity and service health.</p>{{if .}}<div class="error">{{.}}</div>{{end}}<div class="field"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required autofocus></div><div class="field"><label for="password">Password</label><input id="password" type="password" name="password" autocomplete="current-password" required></div><button class="submit" type="submit">Open dashboard</button></form></main></body></html>`))

var adminDashboardTemplate = template.Must(template.New("admin-dashboard").Parse(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>Analytics dashboard | ICT Service Desk</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#17212b;background:#edf1f5}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:linear-gradient(135deg,#e5edf1,#f8f5f0)}.bar{background:#17212b;color:#fff;padding:22px 7vw;display:flex;align-items:center;justify-content:space-between;gap:20px}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#f2a27f;font-weight:700}.bar h1{margin:6px 0 0;font-size:28px}.bar a{color:#fff;text-decoration:none;font-size:13px;font-weight:700;border:1px solid #ffffff55;border-radius:8px;padding:10px 13px}.wrap{width:min(1100px,86vw);margin:42px auto}.intro{margin-bottom:26px}.intro h2{margin:0 0 7px;font-size:27px}.intro p{margin:0;color:#617681}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card{background:#fff;border:1px solid #d6e1e8;border-radius:12px;padding:22px;box-shadow:0 12px 30px #24374610}.label{color:#617681;font-size:13px;font-weight:700}.value{font-size:36px;font-weight:800;color:#123b4a;margin:10px 0}.status{color:#238b82;font-weight:700}.note{margin-top:26px;color:#617681;font-size:13px}@media(max-width:700px){.bar{padding:20px 7vw}.grid{grid-template-columns:1fr}.wrap{width:86vw;margin:28px auto}}
</style></head><body><header class="bar"><div><div class="eyebrow">Operations console</div><h1>Analytics dashboard</h1></div><a href="/admin/logout">Sign out</a></header><main class="wrap"><section class="intro"><h2>Service overview</h2><p>Live activity from the ticket guidance service.</p></section><section class="grid"><article class="card"><div class="label">Guide requests</div><div class="value">{{.GuideRequests}}</div><div class="status">Tracked successfully</div></article><article class="card"><div class="label">Route service</div><div class="value">Online</div><div class="status">Health endpoint responding</div></article><article class="card"><div class="label">Prometheus</div><div class="value">Ready</div><div class="status">Metrics endpoint available</div></article></section><p class="note">Dashboard refreshes every 30 seconds. Detailed metrics are available at <a href="/metrics">/metrics</a>.</p></main></body></html>`))

var loginTemplate = template.Must(template.New("login").Parse(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in | ICT Service Desk</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#17212b;background:#eef3f7}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 10% 0,#d8e9ef,transparent 35%),#eef3f7}.card{width:min(430px,100%);background:#fff;border:1px solid #d6e1e8;border-radius:18px;box-shadow:0 20px 55px #24374618;overflow:hidden}.brand{padding:30px 34px;background:#123b4a;color:#fff}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#9dd9d3;font-weight:700}.brand h1{margin:9px 0 0;font-size:29px;line-height:1.1}.form{padding:30px 34px}.form p{margin:0 0 22px;color:#617681}.field{display:grid;gap:7px;margin-bottom:16px}.field label{font-size:13px;font-weight:700;color:#48636d}.field input{width:100%;border:1px solid #cad8de;border-radius:9px;padding:13px;font:inherit}.field input:focus{outline:0;border-color:#238b82;box-shadow:0 0 0 3px #238b8222}.submit{width:100%;border:0;border-radius:9px;background:#e16b45;color:#fff;padding:14px;font:inherit;font-weight:700;cursor:pointer}.submit:hover{background:#c95532}.error{color:#a53f2e;background:#fff1ed;border-radius:8px;padding:11px;margin-bottom:17px;font-size:14px}</style></head><body><main class="card"><header class="brand"><div class="eyebrow">ICT service desk</div><h1>Sign in to continue</h1></header><form class="form" method="post" action="/login"><p>Access the guided ticket request portal.</p>{{if .}}<div class="error">{{.}}</div>{{end}}<div class="field"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required autofocus></div><div class="field"><label for="password">Password</label><input id="password" type="password" name="password" autocomplete="current-password" required></div><button class="submit" type="submit">Sign in</button></form></main></body></html>`))

var pageTemplate = template.Must(template.New("ticket-guide").Parse(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ticket Guide</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#17212b;background:#eef3f7}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 10% 0,#d8e9ef,transparent 35%),#eef3f7}.shell{width:min(720px,100%);background:#fff;border:1px solid #d6e1e8;box-shadow:0 20px 55px #24374618;border-radius:18px;overflow:hidden}.top{padding:30px 34px 22px;background:#123b4a;color:#fff}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#9dd9d3;font-weight:700}.top h1{margin:8px 0;font-size:clamp(26px,5vw,40px);line-height:1.1}.top p{margin:0;color:#d6e8ea}.content{padding:28px 34px 34px}.progress{height:6px;background:#e4edf0;border-radius:99px;margin-bottom:25px;overflow:hidden}.progress i{display:block;height:100%;background:#e16b45;transition:width .25s ease}.crumbs{min-height:22px;color:#617681;font-size:13px;margin-bottom:10px}.content h2{margin:0 0 18px;font-size:24px}.options{display:grid;gap:10px}.option{width:100%;border:1px solid #cad8de;border-radius:10px;background:#fff;padding:15px 17px;text-align:left;font:inherit;color:inherit;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:.15s}.option:hover,.option:focus-visible{border-color:#e16b45;box-shadow:0 0 0 3px #e16b4522;outline:0;transform:translateY(-1px)}.arrow{color:#e16b45;font-size:20px}.result{background:#f2f8f7;border-left:5px solid #238b82;padding:20px;border-radius:8px}.result strong{display:block;font-size:21px;color:#123b4a;margin-top:5px}.actions{display:flex;justify-content:space-between;gap:12px;margin-top:26px}.actions button{border:0;background:none;color:#48636d;font:inherit;font-weight:700;cursor:pointer;padding:8px 0}.actions button:hover{color:#e16b45}@media(max-width:500px){.top,.content{padding-left:22px;padding-right:22px}}
</style></head><body><main class="shell"><header class="top"><div class="eyebrow">ICT service desk</div><h1>Let's find the right ticket.</h1><p>Answer a few quick questions and we'll point you to the best request type.</p></header><section class="content"><div class="progress"><i id="progress"></i></div><div id="app"></div></section></main><script>
const catalog={{.Catalog}};let path=[];let options=catalog;const app=document.querySelector('#app');const progress=document.querySelector('#progress');
function draw(){const crumbs=path.map(x=>x.name).join(' / ');progress.style.width=Math.min(95,Math.max(8,(path.length+1)*25))+'%';if(!options.length){app.innerHTML='<div class="result"><div class="eyebrow">Recommended ticket</div><strong>'+esc(path[path.length-1].name)+'</strong></div><div class="actions"><button onclick="startOver()">Start over</button></div>';return}app.innerHTML='<div class="crumbs">'+esc(crumbs||'Start here')+'</div><h2>'+(path.length?'Choose the closest match':'What kind of help do you need?')+'</h2><div class="options">'+options.map((x,i)=>'<button class="option" onclick="choose('+i+')"><span>'+esc(x.name)+'</span><span class="arrow">&rsaquo;</span></button>').join('')+'</div><div class="actions">'+(path.length?'<button onclick="back()">&larr; Back</button>':'<span></span>')+'<span></span></div>'}
function choose(i){const selected=options[i];path.push(selected);options=selected.children||[];draw()}function back(){path.pop();options=path.length?(path[path.length-1].children||[]):catalog;draw()}function startOver(){path=[];options=catalog;draw()}function esc(value){return value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}draw();
</script></body></html>`))

func guide(w http.ResponseWriter, _ *http.Request) {
	atomic.AddUint64(&guideRequests, 1)
	encodedCatalog, err := json.Marshal(ticketCatalog)
	if err != nil {
		http.Error(w, "unable to load ticket guide", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_ = pageTemplate.Execute(w, map[string]template.JS{"Catalog": template.JS(encodedCatalog)})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /login", login)
	mux.HandleFunc("POST /login", login)
	mux.HandleFunc("GET /logout", logout)
	mux.HandleFunc("GET /", requireAuth(guide))
	mux.HandleFunc("GET /admin/login", adminLogin)
	mux.HandleFunc("POST /admin/login", adminLogin)
	mux.HandleFunc("GET /admin/logout", adminLogout)
	mux.HandleFunc("GET /admin", requireAdmin(adminDashboard))
	mux.HandleFunc("GET /health", health)
	mux.HandleFunc("GET /metrics", metrics)
	log.Println("Go route service listening on :8080")
	if err := http.ListenAndServe(":8080", mux); err != nil {
		log.Fatal(err)
	}
}
