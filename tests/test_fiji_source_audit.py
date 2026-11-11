from scripts.audit_fiji_pom import inventory


def test_profiles_and_test_scope_are_preserved_without_claiming_runtime_support():
    pom = b'''<project xmlns="http://maven.apache.org/POM/4.0.0">
    <dependencies><dependency><groupId>sample</groupId><artifactId>core</artifactId></dependency>
    <dependency><groupId>sample</groupId><artifactId>test</artifactId><scope>test</scope></dependency></dependencies>
    <profiles><profile><id>windows</id><dependencies><dependency><groupId>sample</groupId><artifactId>core</artifactId><classifier>native</classifier></dependency></dependencies></profile></profiles>
    </project>'''
    result = inventory(pom, "source-ref")
    assert result["declaration_count"] == 3
    assert result["unique_coordinate_count"] == 2
    assert result["declarations"][1]["scope"] == "test"
    assert result["declarations"][2]["profile_id"] == "windows"
    assert not result["runtime_inventory_complete"]
    assert not result["runtime_installed"]


def test_managed_dependencies_are_not_counted_as_runtime_dependencies():
    pom = b'''<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencyManagement><dependencies><dependency><groupId>sample</groupId><artifactId>unused</artifactId></dependency></dependencies></dependencyManagement></project>'''
    assert inventory(pom, "source-ref")["declaration_count"] == 0
