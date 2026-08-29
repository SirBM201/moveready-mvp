param([string]$BackendBase="https://moveready-mvp-production.up.railway.app")
$ErrorActionPreference="Stop"
function Check([string]$Path,[int]$Expected){
  try{$r=Invoke-WebRequest -Method GET -Uri "$BackendBase$Path" -TimeoutSec 60 -UseBasicParsing; $status=[int]$r.StatusCode}
  catch{if($_.Exception.Response){$status=[int]$_.Exception.Response.StatusCode}else{throw}}
  if($status -ne $Expected){throw "$Path returned HTTP $status; expected $Expected"}
  Write-Host "PASS $Path -> HTTP $status" -ForegroundColor Green
}
Check "/api/health" 200
Check "/api/build-info" 200
Check "/api/auth/health" 200
Check "/api/operations/status" 200
Check "/api/jobs/options" 401
Write-Host "LQ20 read-only V1 production acceptance passed. No OTP, write, scan, submission, or external action was performed." -ForegroundColor Green
