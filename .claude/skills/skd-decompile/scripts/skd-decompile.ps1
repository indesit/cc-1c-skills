# skd-decompile v0.2 — Decompile 1C DCS Template.xml to JSON DSL (draft)
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
param(
	[Parameter(Mandatory)]
	[Alias('Path')]
	[string]$TemplatePath,

	[string]$OutputPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- 0. Resolve and validate input ---

if (-not (Test-Path $TemplatePath)) {
	Write-Error "Template not found: $TemplatePath"
	exit 1
}

$TemplatePath = (Resolve-Path $TemplatePath).Path

$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $false
$xmlDoc.Load($TemplatePath)

$root = $xmlDoc.DocumentElement

# Ring 3: not a DataCompositionSchema → fail-fast
if ($root.LocalName -ne 'DataCompositionSchema') {
	Write-Error "Root element <$($root.LocalName)> is not <DataCompositionSchema>. This is not a SKD template (perhaps a spreadsheet — use /mxl-decompile)."
	exit 2
}

# --- 1. Namespace manager ---

$NS_SCHEMA = "http://v8.1c.ru/8.1/data-composition-system/schema"
$NS_COM    = "http://v8.1c.ru/8.1/data-composition-system/common"
$NS_COR    = "http://v8.1c.ru/8.1/data-composition-system/core"
$NS_SET    = "http://v8.1c.ru/8.1/data-composition-system/settings"
$NS_AT     = "http://v8.1c.ru/8.1/data-composition-system/areatemplate"
$NS_V8     = "http://v8.1c.ru/8.1/data/core"
$NS_V8UI   = "http://v8.1c.ru/8.1/data/ui"
$NS_XS     = "http://www.w3.org/2001/XMLSchema"
$NS_XSI    = "http://www.w3.org/2001/XMLSchema-instance"
$NS_CFG    = "http://v8.1c.ru/8.1/data/enterprise/current-config"

$ns = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$ns.AddNamespace("r",      $NS_SCHEMA)
$ns.AddNamespace("dcscom", $NS_COM)
$ns.AddNamespace("dcscor", $NS_COR)
$ns.AddNamespace("dcsset", $NS_SET)
$ns.AddNamespace("dcsat",  $NS_AT)
$ns.AddNamespace("v8",     $NS_V8)
$ns.AddNamespace("v8ui",   $NS_V8UI)
$ns.AddNamespace("xs",     $NS_XS)
$ns.AddNamespace("xsi",    $NS_XSI)

# --- 2. Warnings accumulator ---

$script:warnings = @()
$script:warningCounter = 0

function Add-Warning {
	param([string]$kind, [string]$loc, [string]$detail)
	$script:warningCounter++
	$id = "W{0:D3}" -f $script:warningCounter
	$script:warnings += [ordered]@{ id = $id; kind = $kind; loc = $loc; detail = $detail }
	return $id
}

function New-Sentinel {
	param([string]$kind, [string]$loc, [string]$detail)
	$id = Add-Warning -kind $kind -loc $loc -detail $detail
	return [ordered]@{ '__unsupported__' = [ordered]@{ id = $id; kind = $kind; loc = $loc } }
}

# --- 3. Helpers ---

function Get-Text {
	param($node, [string]$xpath)
	if (-not $node) { return $null }
	$n = $node.SelectSingleNode($xpath, $ns)
	if ($n) { return $n.InnerText } else { return $null }
}

# Extract LocalStringType (multilingual title) → string (if only ru) or hashtable
function Get-MLText {
	param($node)
	if (-not $node) { return $null }
	$items = $node.SelectNodes("v8:item", $ns)
	if ($items.Count -eq 0) { return $null }
	$dict = [ordered]@{}
	foreach ($it in $items) {
		$lang = Get-Text $it "v8:lang"
		$content = Get-Text $it "v8:content"
		if ($lang) { $dict[$lang] = if ($content) { $content } else { "" } }
	}
	if ($dict.Count -eq 1 -and $dict.Contains('ru')) { return $dict['ru'] }
	return $dict
}

# Strip namespace prefix from xsi:type value (e.g. "dcsset:Foo" → "Foo")
function Get-LocalXsiType {
	param($node)
	if (-not $node) { return $null }
	$t = $node.GetAttribute("type", $NS_XSI)
	if ($t -match ':(.+)$') { return $matches[1] }
	return $t
}

# Convert one <v8:Type> element + sibling qualifiers → shorthand type string
function Get-OneTypeShorthand {
	param($typeNode, $qualNumber, $qualString, $qualDate)
	$raw = $typeNode.InnerText.Trim()
	# Strip namespace prefix; check if it's d5p1: (config refs)
	$local = $raw
	if ($raw -match '^([^:]+):(.+)$') {
		$prefix = $matches[1]
		$local  = $matches[2]
		# Resolve prefix → namespace URI
		$uri = $typeNode.GetNamespaceOfPrefix($prefix)
		if ($uri -eq $NS_CFG) {
			return $local   # CatalogRef.X, DocumentRef.X, etc.
		}
		if ($uri -eq $NS_XS) {
			switch ($local) {
				'string'   {
					if ($qualString) {
						$len = [int](Get-Text $qualString "v8:Length")
						$allowed = Get-Text $qualString "v8:AllowedLength"
						if ($len -eq 0) { return 'string' }
						if ($allowed -eq 'Fixed') { return "string($len,fix)" }
						return "string($len)"
					}
					return 'string'
				}
				'boolean'  { return 'boolean' }
				'decimal'  {
					if ($qualNumber) {
						$d = [int](Get-Text $qualNumber "v8:Digits")
						$f = [int](Get-Text $qualNumber "v8:FractionDigits")
						$sign = Get-Text $qualNumber "v8:AllowedSign"
						$signSuf = ''
						if ($sign -eq 'Nonnegative') { $signSuf = ',nonneg' }
						# defaults: 10,2,Any → "decimal"
						if ($d -eq 10 -and $f -eq 2 -and -not $signSuf) { return 'decimal' }
						if ($f -eq 0) { return "decimal($d$signSuf)" }
						return "decimal($d,$f$($signSuf -replace '^,',''))".Replace('decimal(', 'decimal(').Replace(',,',',')
					}
					return 'decimal'
				}
				'dateTime' {
					$frac = if ($qualDate) { Get-Text $qualDate "v8:DateFractions" } else { 'DateTime' }
					switch ($frac) {
						'Date'     { return 'date' }
						'Time'     { return 'time' }
						default    { return 'dateTime' }
					}
				}
				default    { return $local }
			}
		}
		if ($uri -eq $NS_V8) {
			# v8:StandardPeriod, etc.
			return $local
		}
	}
	return $local
}

# valueType → string shorthand OR array of shorthands (composite)
function Get-ValueTypeShorthand {
	param($valueTypeNode)
	if (-not $valueTypeNode) { return $null }
	$types = $valueTypeNode.SelectNodes("v8:Type", $ns)
	if ($types.Count -eq 0) { return $null }
	$qualN = $valueTypeNode.SelectSingleNode("v8:NumberQualifiers", $ns)
	$qualS = $valueTypeNode.SelectSingleNode("v8:StringQualifiers", $ns)
	$qualD = $valueTypeNode.SelectSingleNode("v8:DateQualifiers", $ns)
	$shorts = @()
	foreach ($t in $types) { $shorts += (Get-OneTypeShorthand -typeNode $t -qualNumber $qualN -qualString $qualS -qualDate $qualD) }
	if ($shorts.Count -eq 1) { return $shorts[0] }
	return ,$shorts
}

# <role> → array of @tokens; if non-simple — null + sentinel via $script:roleSentinel
function Get-RoleTokens {
	param($roleNode, [string]$loc)
	if (-not $roleNode) { return $null }
	$tokens = @()
	$hasComplex = $false
	foreach ($child in $roleNode.ChildNodes) {
		if ($child.NodeType -ne [System.Xml.XmlNodeType]::Element) { continue }
		if ($child.NamespaceURI -ne $NS_COM) { $hasComplex = $true; continue }
		switch ($child.LocalName) {
			'dimension' { if ($child.InnerText -eq 'true') { $tokens += '@dimension' } }
			'account'   { if ($child.InnerText -eq 'true') { $tokens += '@account' } }
			'balance'   { if ($child.InnerText -eq 'true') { $tokens += '@balance' } }
			'periodNumber' {
				# Expect periodNumber=1 + periodType=Main → @period
				$pType = Get-Text $roleNode "dcscom:periodType"
				if ($child.InnerText -eq '1' -and $pType -eq 'Main') { $tokens += '@period' } else { $hasComplex = $true }
			}
			'periodType' { } # handled with periodNumber above
			default {
				$hasComplex = $true
			}
		}
	}
	if ($hasComplex) {
		# emit sentinel separately so caller can attach it to field obj
		$null = New-Sentinel -kind 'ComplexRole' -loc $loc -detail 'Роль с дополнительными атрибутами не сворачивается в @-флаг'
	}
	return $tokens
}

# <useRestriction> → array of #tokens
function Get-RestrictionTokens {
	param($urNode)
	if (-not $urNode) { return @() }
	$tokens = @()
	$map = @{ 'field' = '#noField'; 'condition' = '#noFilter'; 'group' = '#noGroup'; 'order' = '#noOrder' }
	foreach ($key in 'field','condition','group','order') {
		$v = Get-Text $urNode "r:$key"
		if ($v -eq 'true') { $tokens += $map[$key] }
	}
	return $tokens
}

# <appearance> → hashtable {param: value}
function Get-AppearanceDict {
	param($appNode)
	if (-not $appNode) { return $null }
	$dict = [ordered]@{}
	$items = $appNode.SelectNodes("dcscor:item", $ns)
	foreach ($it in $items) {
		$p = Get-Text $it "dcscor:parameter"
		$valNode = $it.SelectSingleNode("dcscor:value", $ns)
		if (-not $p -or -not $valNode) { continue }
		# Value can be xs:string, v8ui:HorizontalAlign, v8:LocalStringType, etc.
		$valType = Get-LocalXsiType $valNode
		if ($valType -eq 'LocalStringType') {
			$dict[$p] = Get-MLText $valNode
		} else {
			$dict[$p] = $valNode.InnerText
		}
	}
	return $dict
}

# Build a field JSON entry (shorthand if possible, object form otherwise)
function Build-Field {
	param($fieldNode, [string]$loc)
	$dataPath = Get-Text $fieldNode "r:dataPath"
	$fieldName = Get-Text $fieldNode "r:field"
	$titleNode = $fieldNode.SelectSingleNode("r:title", $ns)
	$title = Get-MLText $titleNode
	$valueTypeNode = $fieldNode.SelectSingleNode("r:valueType", $ns)
	$typeShort = Get-ValueTypeShorthand $valueTypeNode
	$roleTokens = Get-RoleTokens $fieldNode.SelectSingleNode("r:role", $ns) "$loc/role"
	$restrictTokens = Get-RestrictionTokens $fieldNode.SelectSingleNode("r:useRestriction", $ns)
	$appNode = $fieldNode.SelectSingleNode("r:appearance", $ns)
	$appearance = Get-AppearanceDict $appNode
	$presExpr = Get-Text $fieldNode "r:presentationExpression"

	$needsObject = $title -or $appearance -or $presExpr -or ($typeShort -is [array])

	if (-not $needsObject) {
		# shorthand: "Name: type @role #restrict"
		$parts = @($fieldName)
		if ($typeShort) { $parts[0] = "$fieldName`: $typeShort" }
		if ($roleTokens) { $parts[0] += ' ' + ($roleTokens -join ' ') }
		if ($restrictTokens) { $parts[0] += ' ' + ($restrictTokens -join ' ') }
		# dataPath ≠ field — fall back to object form
		if ($dataPath -and $dataPath -ne $fieldName) {
			# unusual case; use object form
		} else {
			return $parts[0]
		}
	}

	$obj = [ordered]@{ field = $fieldName }
	if ($dataPath -and $dataPath -ne $fieldName) { $obj['dataPath'] = $dataPath }
	if ($title) { $obj['title'] = $title }
	if ($typeShort) { $obj['type'] = $typeShort }
	if ($roleTokens) {
		if ($roleTokens.Count -eq 1) { $obj['role'] = $roleTokens[0] -replace '^@','' }
		else { $obj['role'] = ($roleTokens | ForEach-Object { $_ -replace '^@','' }) }
	}
	if ($restrictTokens) { $obj['restrict'] = ($restrictTokens | ForEach-Object { $_ -replace '^#','' }) }
	if ($presExpr) { $obj['presentationExpression'] = $presExpr }
	if ($appearance) { $obj['appearance'] = $appearance }
	return $obj
}

# --- 4. dataSources ---

$dataSources = @()
$dsourceNodes = $root.SelectNodes("r:dataSource", $ns)
foreach ($dsn in $dsourceNodes) {
	$nm = Get-Text $dsn "r:name"
	$tp = Get-Text $dsn "r:dataSourceType"
	$dataSources += [ordered]@{ name = $nm; type = $tp }
}
# Default: single ИсточникДанных1/Local → omit from output
$emitDataSources = $true
if ($dataSources.Count -eq 1 -and $dataSources[0].name -eq 'ИсточникДанных1' -and $dataSources[0].type -eq 'Local') {
	$emitDataSources = $false
}

# --- 5. dataSets ---

$dataSets = @()
$dsNodes = $root.SelectNodes("r:dataSet", $ns)
foreach ($dsNode in $dsNodes) {
	$xsiType = Get-LocalXsiType $dsNode
	$name = Get-Text $dsNode "r:name"
	$ds = [ordered]@{ name = $name }

	switch ($xsiType) {
		'DataSetQuery' {
			$ds['query'] = Get-Text $dsNode "r:query"
		}
		'DataSetObject' {
			$ds['objectName'] = Get-Text $dsNode "r:objectName"
		}
		'DataSetUnion' {
			$ds['__unsupported__'] = (New-Sentinel -kind 'DataSetUnion' -loc "dataSet[$name]" -detail 'Реализуется в слое 15')['__unsupported__']
		}
		default {
			$ds['__unsupported__'] = (New-Sentinel -kind "DataSetType:$xsiType" -loc "dataSet[$name]" -detail "Неизвестный тип набора данных")['__unsupported__']
		}
	}

	# Fields
	$fieldNodes = $dsNode.SelectNodes("r:field", $ns)
	if ($fieldNodes.Count -gt 0) {
		$fields = @()
		$fi = 0
		foreach ($fn in $fieldNodes) {
			$fxsi = Get-LocalXsiType $fn
			if ($fxsi -ne 'DataSetFieldField') {
				$fields += (New-Sentinel -kind "FieldType:$fxsi" -loc "dataSet[$name]/field[$fi]" -detail 'Тип поля не DataSetFieldField')
			} else {
				$fields += (Build-Field -fieldNode $fn -loc "dataSet[$name]/field[$fi]")
			}
			$fi++
		}
		$ds['fields'] = $fields
	}

	# dataSource attachment — omit if matches default
	$dsSrc = Get-Text $dsNode "r:dataSource"
	if ($emitDataSources -and $dsSrc) { $ds['dataSource'] = $dsSrc }

	$dataSets += $ds
}

# --- 6. Build top-level JSON object ---

$out = [ordered]@{}
if ($emitDataSources) { $out['dataSources'] = $dataSources }
$out['dataSets'] = $dataSets

# --- 7. Serialize ---

$json = $out | ConvertTo-Json -Depth 32

# Unescape \uXXXX → UTF-8 literals
$json = [regex]::Replace($json, '\\u([0-9a-fA-F]{4})', {
	param($m)
	[char][int]("0x" + $m.Groups[1].Value)
})

if ($OutputPath) {
	if (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
		$OutputPath = Join-Path (Get-Location).Path $OutputPath
	}
	$enc = New-Object System.Text.UTF8Encoding($false)
	[System.IO.File]::WriteAllText($OutputPath, $json, $enc)

	if ($script:warnings.Count -gt 0) {
		$wPath = [System.IO.Path]::ChangeExtension($OutputPath, $null).TrimEnd('.') + '.warnings.md'
		$sb = New-Object System.Text.StringBuilder
		[void]$sb.AppendLine("# skd-decompile warnings")
		[void]$sb.AppendLine("")
		[void]$sb.AppendLine("Source: $TemplatePath")
		[void]$sb.AppendLine("")
		foreach ($w in $script:warnings) {
			[void]$sb.AppendLine("- **$($w.id)** ($($w.kind)) at `$($w.loc)`: $($w.detail)")
		}
		[System.IO.File]::WriteAllText($wPath, $sb.ToString(), $enc)
		Write-Host "Warnings: $wPath ($($script:warnings.Count) issue(s))" -ForegroundColor Yellow
	}

	[Console]::Error.WriteLine("Decompiled: dataSets=$($dataSets.Count), warnings=$($script:warnings.Count)")
} else {
	Write-Output $json
	if ($script:warnings.Count -gt 0) {
		[Console]::Error.WriteLine("Warnings ($($script:warnings.Count)):")
		foreach ($w in $script:warnings) {
			[Console]::Error.WriteLine("  $($w.id) [$($w.kind)] $($w.loc): $($w.detail)")
		}
	}
}
