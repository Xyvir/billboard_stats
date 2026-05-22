param(
    [string]$AlbumsDir = "c:\Users\temp\billboard\billboard_stats\billboard_stats\data\albums",
    [string]$SongsDir = "c:\Users\temp\billboard\billboard_stats\billboard_stats\data\songs",
    [string]$ScriptPath = "c:\Users\temp\billboard\billboard_stats\hydrate_album.py"
)

Write-Host "Starting Album Hydration Pipeline..."
$albumFiles = Get-ChildItem -Path $AlbumsDir -Filter "*.json" | Sort-Object Name
Write-Host "Found $($albumFiles.Count) total album files."

$batchCount = 0
$batchSize = 40

foreach ($file in $albumFiles) {
    # Check if hydrated
    $content = Get-Content $file.FullName -Raw
    if ($content -notmatch '"tracks"\s*:') {
        
        # Run python script
        & python $ScriptPath $file.FullName $SongsDir
        
        $batchCount++
        
        if ($batchCount -ge $batchSize) {
            Write-Host "Batch of $batchSize reached. Committing and pushing to git..."
            git add $AlbumsDir
            git commit -m "Hydrated $batchSize albums"
            git push
            $batchCount = 0
        }
    }
}
