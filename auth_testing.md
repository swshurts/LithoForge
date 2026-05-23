# Auth-Gated App Testing Playbook

## Step 1: Create Test User & Session
```bash
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```bash
curl -X GET "$API_URL/api/auth/me" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"

curl -X GET "$API_URL/api/presets" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"

curl -X POST "$API_URL/api/presets" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -d '{"name":"Test","config":{},"filaments":[],"vibrancy":0.5}'
```

## Step 3: Browser Testing
```javascript
await page.context.add_cookies([{
  "name": "session_token",
  "value": "YOUR_SESSION_TOKEN",
  "domain": "your-app.com",
  "path": "/",
  "httpOnly": true,
  "secure": True,
  "sameSite": "None"
}])
await page.goto("https://your-app.com")
```

## Checklist
- [ ] User document has `user_id` field (custom UUID, MongoDB's `_id` is separate)
- [ ] Session `user_id` matches user's `user_id` exactly
- [ ] All queries use `{"_id": 0}` projection
- [ ] Backend queries use `user_id` (not `_id` or `id`)
- [ ] `/api/auth/me` returns user data
- [ ] Anonymous users can still use the app (auth is opt-in for this app)
- [ ] Presets sync across devices when logged in

## App-Specific Notes (Lithoforge)
This app is **NOT auth-gated**. Login is purely opt-in to sync presets across devices.
- Anonymous users still see/use built-in presets and can save to localStorage
- Logged-in users see their cloud-saved presets in addition to built-ins
- After login, localStorage presets should auto-migrate to backend (one-time)
