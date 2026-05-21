Write-Host "Starting continuous 'act' and 'git push' loop. Press Ctrl+C to stop." -ForegroundColor Cyan

while ($true) {
    Write-Host "`n======================================" -ForegroundColor Yellow
    Write-Host "Running act..." -ForegroundColor Yellow
    
    # Run act with the bind flag on your specified workflow file
    act --bind

    Write-Host "`n'act' execution finished. Checking for changes..." -ForegroundColor Yellow
    
    # Check if there are any modified, added, or deleted files
    if (git status --porcelain) {
        git add .
        git commit -m "Automated commit after local act execution"
        git push
        Write-Host "Changes pushed successfully!" -ForegroundColor Green
    } else {
        Write-Host "No changes to commit." -ForegroundColor DarkGray
    }

    Write-Host "`nWaiting 5 seconds before the next run. Press Ctrl+C to abort..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
}
