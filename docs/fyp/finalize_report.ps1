# Opens the generated .docx in Word, fills in the table of contents / lists / page numbers,
# saves it, and exports a PDF next to it.
param([string]$Docx = (Join-Path $PSScriptRoot "EchoLearn FYP Final Document.docx"))
$pdf = [System.IO.Path]::ChangeExtension($Docx, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx)
    # table-of-contents styles: Times New Roman 12, indented by level
    $spec = @{ -20 = 0.0; -21 = 0.25; -22 = 0.5 }
    foreach ($id in $spec.Keys) {
        $s = $doc.Styles.Item($id)
        $s.Font.Name = "Times New Roman"; $s.Font.Size = 12; $s.Font.Bold = 0
        $s.ParagraphFormat.LeftIndent = $word.InchesToPoints($spec[$id])
        $s.ParagraphFormat.SpaceBefore = 0
        $s.ParagraphFormat.SpaceAfter = 4
        $s.ParagraphFormat.LineSpacingRule = 0
        $s.ParagraphFormat.Alignment = 0
    }
    $doc.Repaginate()
    $null = $doc.Fields.Update()
    foreach ($t in $doc.TablesOfContents) { $null = $t.Update() }
    $doc.Repaginate()
    $null = $doc.Fields.Update()
    foreach ($t in $doc.TablesOfContents) { $null = $t.Update() }
    $doc.Repaginate()
    # the empty paragraphs after the TOC (field end + section break) must not spill onto a page of their own
    $sec2 = $doc.Sections.Item(2).Range
    $n = $sec2.Paragraphs.Count
    foreach ($i in @(($n - 1), $n)) {
        $q = $sec2.Paragraphs.Item($i)
        if ($q.Range.Text.Trim().Length -eq 0) {
            $q.Range.Font.Size = 1
            $q.SpaceBefore = 0; $q.SpaceAfter = 0
            $q.LineSpacingRule = 0
        }
    }
    $doc.Repaginate()
    $pages = $doc.ComputeStatistics(2)
    $doc.Save()
    $doc.ExportAsFixedFormat($pdf, 17)
    Write-Output "pages=$pages"
    Write-Output "pdf=$pdf"
    $doc.Close(0)
}
finally {
    $word.Quit()
}
